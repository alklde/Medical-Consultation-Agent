from mcp.server.fastmcp import FastMCP

mcp = FastMCP("roymcpdemo")

@mcp.tool()
def patient_info(user_id: str):
    """获取指定患者的诊断记录
        Args:
            user_id (str): 患者ID
        Returns:
            用户的诊断记录
    """
    return [{"user_id": user_id, "diagnosis_info": "甲状腺肿大", "data": "2023-01-01"},
            {"user_id": user_id, "diagnosis_info": "鼻炎", "data": "2023-01-02"},
            {"user_id": user_id, "diagnosis_info": "过敏性皮炎", "data": "2025-01-03"},
            {"user_id": user_id, "diagnosis_info": "韧带撕裂", "data": "2026-01-04"}]

if __name__ == "__main__":
    mcp.run(transport="streamable-http")