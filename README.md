# Medical Consultation Agent

基于 LangGraph 与 MCP 的医疗问诊多智能体示例。系统通过一个 Supervisor 节点对用户问题进行分类，并路由到不同的子 Agent 处理就诊记录查询、初步诊断和医生信息查询等任务。

## 功能

- **Supervisor 路由**：对用户问题分类为 `guidance`、`diagnosis`、`doctor` 或 `error`，并分发到对应节点。
- **就诊记录查询（guidance）**：通过 MCP 工具获取患者历史就诊记录，并按时间倒序返回最近三条。
- **初步诊断（diagnosis）**：基于 Redis 向量库检索医学百科知识，由大模型生成诊断建议。
- **医生信息查询（doctor）**：由大模型生成 MySQL 查询语句，并对输出中的邮箱进行脱敏处理。
- **其他问题（error）**：返回无法回答的提示。

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `Doctor.py` | 主程序，构建 LangGraph 状态图并编排各 Agent |
| `DiagnosisLoader.py` | 加载医学百科数据并写入 Redis 向量库 |
| `DiagnosisRetriva.py` | 独立的诊断知识检索示例 |
| `guidanceMCP.py` | 基于 FastMCP 的就诊记录查询工具服务 |

## 环境依赖

```bash
pip install langchain langchain-openai langchain-community langchain-redis \
            langchain-mcp-adapters langgraph mcp python-dotenv dashscope
```

同时需要：

- 本地 Redis 服务（默认 `redis://localhost:6379`）
- 可访问的 OpenAI 兼容大模型接口（通过环境变量配置）

## 环境变量

在项目根目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
DATA_MODEL=your_model_name
DATA_BASE_URL=your_model_base_url
DATA_API_KEY=your_model_api_key
```

## 使用方法

1. 启动 MCP 服务（就诊记录查询）：

   ```bash
   python guidanceMCP.py
   ```

2. 将医学百科数据导入向量库（需确保 `../data/test_encyclopedia.csv` 存在）：

   ```bash
   python DiagnosisLoader.py
   ```

3. 运行主程序：

   ```bash
   python Doctor.py
   ```

   可在 `Doctor.py` 的 `__main__` 中修改示例 `query`，例如：

   ```python
   query = "查找001号病人的就诊记录"
   ```

## 工作流程

```
START -> supervisor_node
             |
             +-- guidance_node  --+
             +-- diagnosis_node --+
             +-- doctor_node    --+
             +-- error_node     --+
             |
            END
```

各业务节点执行完成后会返回 `supervisor_node`，由 Supervisor 判断任务结束并进入 `END`。