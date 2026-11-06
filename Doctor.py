import asyncio
from typing import TypedDict, Annotated

from langchain.agents import create_agent
from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, START, END, add_messages

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import PIIMiddleware
from dotenv import load_dotenv
import os
load_dotenv()

from DiagnosisLoader import vector_store

llm = ChatOpenAI(
    model=os.getenv("DATA_MODEL"),
    base_url=os.getenv("DATA_BASE_URL"),
    api_key=os.getenv("DATA_API_KEY"),
)

doctor_prompts = """
    你是一个医生信息助手，负责处理用户查询医生信息的请求，并生成对应的SQL语句。
    医生信息表的建表语句如下：
    CREATE TABLE doctor (
        doctor_id VARCHAR(20) PRIMARY KEY,
        name VARCHAR(20),
        department VARCHAR(20),
        phone VARCHAR(20),
        email VARCHAR(20),
        address VARCHAR(20),
        age INT
    );
    生成的SQL语句的要求如下：
        1. 所有SQL语句必须能够在MySQL中正常执行。
        2. 医生信息和科室信息都切换成英文进行查询，如果用户的询问的人名或地名是中文，转换成拼音进行查询，拼音要连在一起，不能有间隔。
        3. 所有SQL语句都必须包含中文注释。
        4. 返回结果中，只包含SQL语句及其注释，不包含任何其他内容。
    例如：用户询问”呼吸科张三医生的信息”，则生成的SQL语句如下：
    SELECT * FROM doctor WHERE department = 'respiratory' AND name = 'zhangsan'
"""

doctor_agent = create_agent(
    model=llm,
    system_prompt=doctor_prompts,
    middleware=[PIIMiddleware(
        "email",
        strategy="mask",
        apply_to_output=True,
    )],
)

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    type: str

# 任务统筹
def supervisor_node(state: State):
    print(">>>supervisor_node")
    # 对用户问题分类
    system_prompt = """
        你是一个专业的客服助手，负责对用户的问题进行分类，并将任务分给其他的Agent执行。
        如果用户的问题是和病人的就诊记录相关，就返回 guidance 。
        如果用户的问题是和病人的初步诊断结果相关，就返回 diagnosis 。
        如果用户的问题是和病人的医生信息相关，就返回 doctor 。
        如果用户的问题是其他任务，就返回 error 。
        除了这几个选项外，不要返回任何其他内容。
    """
    prompts = [{"role": "system", "content": system_prompt},
               {"role": "user", "content": state["messages"][0].content}]

    print(prompts)
    # 如果问题已被其他节点处理完，直接返回
    if "type" in state:
        return {"type": END}
    else:
        res = llm.invoke(prompts)
        type_res = res.content
        return {"type": type_res}


# 获取诊断记录
def guidance_node(state : State):
    print(">>>guidance_node")
    query = state["messages"][0].content

    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient(
        {
            "ray-app": {
                "url": "http://localhost:8000/mcp",
                "transport": "streamable-http"
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    guidance_agent = create_agent(
        model=llm,
        system_prompt="你是一个专业的导诊护士，负责根据病人的编号，获取病人的就诊记录，并将就诊记录按时间进行倒序排序，取出最近的三个记录。",
        tools=tools,
    )
    res = asyncio.run(guidance_agent.ainvoke({"messages": [{"role": "user", "content": query}]}))
    print(">>>guidance_agent", res["messages"][-1].content)
    return {"messages": [{"role": "assistant", "content": res["messages"][-1].content}]}

# 初步诊断结果
def diagnosis_node(state: State):
    print(">>>diagnosis_node")
    query = state["messages"][0].content

    scored_res = vector_store.similarity_search(query, k=3)
    samples = []
    for doc, score in scored_res:
        samples.append(doc.page_content)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """
            你是一位经验丰富的医生，负责根据下面的参考信息回答用户的问题。
            参考信息：
                {samples}
            请用中文回答。
        """),
        ("user", "{query}"),
    ])
    prompt = prompt_template.format(samples=samples, query=query)
    res = llm.invoke(prompt)
    print(">>>diagnosis_node", res.content)
    return {"messages": [{"role": "assistant", "content": res.content}]}


# 获取医生信息
def doctor_node(state: State):
    print(">>>doctor_node")
    # 生成SQL语句 -- 把建表信息和问题一起发给LLM
    
    query = state["messages"][0].content
    
    res = doctor_agent.invoke({"messages": [{"role": "user", "content": query}]})
    sql = res["messages"][-1].content
    print(">>>sql", sql)
    return {"messages": [{"role": "assistant", "content": sql}]}


# 其他任务
def error_node(state: State):
    print(">>>error_node")
    return {"messages": [{"role": "assistant", "content": "我无法回答这个问题"}]}

# 选择不同节点
def routing_fun(state: State):
    print(">>>routing_fun", state["type"])
    if state["type"] == "guidance":
        return "guidance_node"
    elif state["type"] == "diagnosis":
        return "diagnosis_node"
    elif state["type"] == "doctor":
        return "doctor_node"
    elif state["type"] == END:
        return END
    else:
        return "error_node"

builder = StateGraph(State)

builder.add_node("supervisor_node", supervisor_node)
builder.add_node("guidance_node", guidance_node)
builder.add_node("diagnosis_node", diagnosis_node)
builder.add_node("doctor_node", doctor_node)
builder.add_node("error_node", error_node)

builder.add_edge(START, "supervisor_node")
builder.add_conditional_edges("supervisor_node", routing_fun, ["guidance_node", "diagnosis_node", "doctor_node", "error_node", END])
builder.add_edge("guidance_node", "supervisor_node")
builder.add_edge("diagnosis_node", "supervisor_node")
builder.add_edge("doctor_node", "supervisor_node")
builder.add_edge("error_node", "supervisor_node")

graph = builder.compile()

if __name__ == "__main__":
    query = "查找001号病人的就诊记录"
    # query = "膝盖韧带撕裂怎么处理"
    # query = "我要了解内分泌科锤子医生的信息"
    # query = "今天天气怎么样"

    res = graph.invoke({"messages": [{"role": "user", "content": query}]})
    print(res)