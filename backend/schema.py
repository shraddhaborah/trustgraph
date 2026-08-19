from pydantic import BaseModel, Field
from typing import List, Literal

class EntityNode(BaseModel):
    id: str = Field(description="Unique snake_case ID, e.g., 'grantor_john'")
    name: str
    role: Literal["Grantor", "Trustee", "Beneficiary", "Co-Trustee"]
    details: str = Field(description="Brief status or entitlement details")

class EdgeRelationship(BaseModel):
    source_id: str
    target_id: str
    label: Literal["TRANSFERS_TO", "CONTROLS", "APPOINTS", "DISTRIBUTES_TO"]
    conditions: str = Field(description="e.g., 'Upon reaching age 35' or 'Subject to Crummey power'")

class TrustGraphData(BaseModel):
    trust_name: str
    nodes: List[EntityNode]
    edges: List[EdgeRelationship]