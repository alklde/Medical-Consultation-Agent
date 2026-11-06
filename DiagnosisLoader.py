"""
诊断记录加载器
"""
from langchain_redis import RedisConfig, RedisVectorStore
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_community.embeddings import DashScopeEmbeddings

embeddings = DashScopeEmbeddings(
    model="text-embedding-v3",
    dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
)

redis_url = "redis://localhost:6379"

redis_config = RedisConfig(redis_url=redis_url, index_name="diagnosis_guide")
vector_store = RedisVectorStore(config=redis_config, embeddings=embeddings)
if __name__ == "__main__":
    lines = []
    with open("../data/test_encyclopedia.csv", "r") as f:
        for line in f:
            lines.append(line.strip())

    vector_store.add_documents(lines)
