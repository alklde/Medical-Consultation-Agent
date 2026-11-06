# 检索
from DiagnosisLoader import vector_store
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv
load_dotenv()

query = "膝盖损伤怎么治疗"
prompt_template = ChatPromptTemplate.from_messages([
    ("system", """
        你是一位经验丰富的医生，负责根据下面的参考信息回答用户的问题。
        参考信息：
            {samples}
        请用中文回答。
    """),
    ("user", "{query}"),
])

if __name__ == "__main__":
    samples = []
    scored_results = vector_store.similarity_search(query, k=3)
    for doc, score in scored_results:
        samples.append(doc.page_content)

    prompt = prompt_template.format(samples=samples, query=query)
    print(prompt)
    llm = ChatOpenAI(
        model=os.getenv("DATA_MODEL"),
        base_url=os.getenv("DATA_BASE_URL"),
        api_key=os.getenv("DATA_API_KEY"),
    )
    res = llm.invoke(prompt)
    print(res.content)
