from src.data.gateway import DataGateway
from src.schemas.handoff import OrderSellerFacts
from src.llm_client import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.retry_utils import retry_with_backoff
import json

class OrderSellerAgent:
    def __init__(self):
        self.gateway = DataGateway()
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are the Order & Seller Agent. You receive raw order and seller data extracted from the database. Your job is to parse this data and format it into the exact requested JSON schema. Do not modify amounts, dates, or IDs. Only output the valid JSON."),
            ("user", "Case ID: {case_id}\nOrder ID: {order_id}\nRaw Database Facts:\n{facts}")
        ])
        # PydanticOutputParser with fallback to simple JSON if needed. with_structured_output handles function calling directly for Gemini.
        self.chain = self.prompt | self.llm.with_structured_output(OrderSellerFacts)
        
    @retry_with_backoff(max_retries=10, initial_delay=30)
    def investigate(self, case_id: str, claimed_order_id: str) -> OrderSellerFacts:
        facts = self.gateway.get_order_seller_facts(claimed_order_id)
        return self.chain.invoke({
            "case_id": case_id,
            "order_id": claimed_order_id,
            "facts": facts.model_dump_json(indent=2)
        })
