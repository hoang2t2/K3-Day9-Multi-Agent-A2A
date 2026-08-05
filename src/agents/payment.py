from src.data.gateway import DataGateway
from src.schemas.handoff import PaymentFacts
from src.llm_client import get_llm
from langchain_core.prompts import ChatPromptTemplate

from src.retry_utils import retry_with_backoff

class PaymentAgent:
    def __init__(self):
        self.gateway = DataGateway()
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are the Payment Agent. You receive raw payment data extracted from the database. Parse this data and format it into the requested JSON schema accurately. Do not modify amounts or IDs."),
            ("user", "Case ID: {case_id}\nOrder ID: {order_id}\nRaw Database Facts:\n{facts}")
        ])
        self.chain = self.prompt | self.llm.with_structured_output(PaymentFacts)
        
    @retry_with_backoff(max_retries=10, initial_delay=30)
    def investigate(self, case_id: str, claimed_order_id: str, item_total: float, freight_total: float) -> PaymentFacts:
        facts = self.gateway.get_payment_facts(claimed_order_id, item_total, freight_total)
        return self.chain.invoke({
            "case_id": case_id,
            "order_id": claimed_order_id,
            "facts": facts.model_dump_json(indent=2)
        })
