from datetime import datetime
from typing import List, Optional, Dict, Any, TypedDict, Union
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.pydantic_v1 import BaseModel, Field
import config
from conversation_manager.state import AvailableSlot
from langchain.tools import tool
from langchain.text import detect
from services import cal_service



class Assisant:
    def __init__(self, customer_email: str, customer_name: str):
        self.llm_model = self.get_llm_instance()
        self.event_type_slug = config.CAL_COM_EVENT_TYPE_SLUG
        self.cal_username = config.CAL_COM_USERNAME
        self.cal_api_key = config.CAL_COM_API_KEY
        self.customer_email = customer_email
        self.customer_name = customer_name

    def get_llm_instance(self) -> Optional[ChatGoogleGenerativeAI]:
        """Returns an instance of the LangChain Gemini model."""
        if not config.GOOGLE_GEMINI_API_KEY:
            print("LLM model cannot be initialized: GOOGLE_GEMINI_API_KEY is not set.")
            return None
        try:
            model = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.6,
                top_p=1,
                top_k=1,
                max_output_tokens=1024,
                google_api_key=config.GOOGLE_GEMINI_API_KEY
            )
            model_with_tools = model.bind_tools([self.get_event_type_details, self.get_available_slots, self.book_a_meeting])
            return model_with_tools
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
            return None

    def get_system_instructions(self) -> str:
        return """
You are professional assistant of Olli from OTL.fi. 
We are a IT services company that focuses on creating AI solutions to automate menial work in companies.
Olli has expertise in automating backoffice work in companies.

Your main task is to help our customers with their questions and requests. Only help with OTL.fi related questions.
Your main goal is to book meetings with our customers. You have been provided with tools to help you with this.

You are able to book meetings with the following tools:
- get_event_type_details
- get_available_slots
- book_slot
"""

    def start_conversation(self, customer_message: str) -> str:
        """Starts a new conversation with the customer."""
        # Get event type details once during initialization
        system_message = SystemMessage(content=self.get_system_instructions())
        human_message = HumanMessage(content=customer_message)

        response = self.llm_model.invoke([system_message, human_message])
        return response.content

    def continue_conversation(customer_message: str, chat_history: List[tuple[str, str]]) -> str:
        """Continues a conversation with the customer."""
        # Get event type details once during initialization
        message_history = []
        
        for message in chat_history:
            message_history.append(BaseMessage(type=message[0], content=message[1]))

    @tool
    def get_event_type_details(username: str, event_type_slug: str) -> Optional[Dict[str, Any]]:
        """Get details about an event type."""
        return cal_service.get_event_type_details(username, event_type_slug)

    @tool
    def get_available_slots(username: str, event_type_slug: str) -> List[AvailableSlot]:
        """Get available slots for an event type."""
        return cal_service.get_available_slots(username, event_type_slug)

    @tool
    def book_a_meeting(username: str, event_type_slug: str, slot_id: str) -> bool:
        """Book a slot for an event type."""
        return cal_service.book_slot(username, event_type_slug, slot_id)



