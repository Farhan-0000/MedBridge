from pydantic import BaseModel

class GeneratedCitation(BaseModel):
    marker: str
    chunk_id: str
    source: str
    section: str
    excerpt: str

class ResponseGeneratorOutput(BaseModel):
    response_text: str
    citations: list[GeneratedCitation]
