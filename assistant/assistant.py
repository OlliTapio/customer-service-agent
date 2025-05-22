from datetime import datetime
from typing import List, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
import pytz
from assistant.types import ChatMessage
import config
from conversation_manager.state import AvailableSlot
from helpers.booking_helpers import format_slots, select_slots
from services import cal_service



class Assistant:
    def __init__(self, customer_email: str):
        self.llm_model = self.get_llm_instance()
        self.event_type_slug = config.CAL_COM_EVENT_TYPE_SLUG
        self.cal_username = config.CAL_COM_USERNAME
        self.cal_api_key = config.CAL_COM_API_KEY
        self.customer_email = customer_email

    def get_llm_instance(self) -> Optional[ChatGoogleGenerativeAI]:
        """Returns an instance of the LangChain Gemini model."""
        if not config.GOOGLE_GEMINI_API_KEY:
            raise ValueError("Error: GOOGLE_GEMINI_API_KEY is not configured for LLM initialization.")
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
        base_instructions = """
You are professional assistant of Olli from OTL.fi. 
We are a IT services company that focuses on creating AI solutions to automate menial work in companies.
Olli has expertise in automating backoffice work in companies.

Your main task is to help our customers with their questions and requests. Only help with OTL.fi related questions.
Your main goal is to book meetings with our customers. You have been provided with tools to help you with this.

You operate in Helsinki timezone. You are able to request the current time of day in Helsinki with the get_current_time tool.

You are able to book meetings with the following tools:
- get_event_type_details
- get_available_slots
- book_slot
- get_booking_link
- get_current_time

"""
        email_instructions = """
You are responding to an email. Your answer should be an email body. Formatting will be handled by the email client.

There might be delay between the messages you send so you should check the current time when booking a meeting.
        """
        return base_instructions + email_instructions


    def handle_conversation(self, customer_message: str, chat_history: List[ChatMessage] = None) -> tuple[str, List[BaseMessage]]:
        """Handles a conversation with the customer, either starting a new one or continuing an existing one.
        
        Returns:
            tuple containing:
            - The assistant's response content
            - The complete message history (including system message)
        """
        message_history = []
        
        # If no chat history exists, add system message
        if not chat_history:
            message_history.append(SystemMessage(content=self.get_system_instructions()))
        else:
            # Convert existing chat history to BaseMessage format
            for message in chat_history:
                message_history.append(BaseMessage(type=message.role, content=message.content))

        # Add the new customer message
        message_history.append(HumanMessage(content=customer_message))
        
        # Get response from LLM
        response = self.llm_model.invoke(message_history)
        message_history.append(BaseMessage(type="assistant", content=response.content))
        
        return response.content, message_history

    @tool(description="Get details about an event type.")
    def get_event_type_details(username: str, event_type_slug: str) -> Optional[Dict[str, Any]]:
        response = cal_service.get_event_type_details_v2(
            username, event_type_slug)
        return response.get("id")

    @tool(description="Get available slots for an event type.")
    def get_available_slots(username: str, event_type_id: str) -> List[AvailableSlot]:
        raw_slots = cal_service.get_available_slots_v1(
            api_key=config.CAL_COM_API_KEY,
            event_type_id=str(event_type_id),
            days_to_check=14,
            target_timezone="Europe/Helsinki")
        selected_slots = select_slots(raw_slots)
        return format_slots(selected_slots)

    @tool(description="Book a slot for an event type. meeting_description should describe the purpose of the meeting.")
    def book_a_meeting(username: str, event_type_id: str, slot_time: datetime, meeting_description: str) -> bool:
        return cal_service.create_booking(
            event_type_id=event_type_id,
            slot_time=slot_time.isoformat(),
            user_email=self.customer_email,
            user_name=self.customer_name,
            event_type_slug=self.event_type_slug,
            notes=meeting_description
        )
    
    @tool(description="Get the booking link for a meeting.")
    def get_booking_link(username: str, event_type_id: str, slot_time: datetime) -> str:
        return cal_service.get_booking_link(
            username=username,
            event_type_id=event_type_id,
            slot_time=slot_time.isoformat()
        )
    
    @tool(description="Get the current time and date in Helsinki.")
    def get_current_time(self) -> str:
        now = datetime.now()
        #to helsinki timezone taking into account daylight saving time
        helsinki_timezone = pytz.timezone('Europe/Helsinki')
        helsinki_time = now.astimezone(helsinki_timezone)
        return helsinki_time.isoformat()


