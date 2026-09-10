"""
Streamlit Session State & Query Parameter Management (TASK-25, Module M-20).

Manages conversation session state and synchronizes with Streamlit's URL
query parameters (?session_id=...) to support persistent, bookmarkable sessions.

Technical Specification Part I §3.2, §3.3.
"""
from typing import Any, Optional, Union
import uuid

import streamlit as st

from medbridge.frontend.services.api_client import APIClient


class SessionManager:
    """Manages session lifecycle and state synchronization in Streamlit."""

    @staticmethod
    def get_session_id() -> Optional[uuid.UUID]:
        """
        Retrieve active session UUID from st.session_state or st.query_params.
        
        If found in query params but not in state, synchronizes into session state.
        Returns None if no valid session is found.
        """
        # 1. Check Streamlit session state
        if "session_id" in st.session_state:
            val = st.session_state["session_id"]
            if isinstance(val, uuid.UUID):
                return val
            try:
                parsed_uuid = uuid.UUID(str(val))
                st.session_state["session_id"] = parsed_uuid
                return parsed_uuid
            except ValueError:
                pass

        # 2. Check URL query parameters (?session_id=...)
        query_param_val = st.query_params.get("session_id")
        if query_param_val:
            try:
                parsed_uuid = uuid.UUID(str(query_param_val))
                st.session_state["session_id"] = parsed_uuid
                st.query_params["session_id"] = str(parsed_uuid)
                return parsed_uuid
            except ValueError:
                # Remove invalid query parameter
                if "session_id" in st.query_params:
                    del st.query_params["session_id"]

        return None

    @staticmethod
    def set_session_id(session_id: Union[uuid.UUID, str]) -> uuid.UUID:
        """
        Set active session UUID in both st.session_state and st.query_params.
        
        Args:
            session_id: UUID instance or valid UUID string.
            
        Returns:
            Normalized UUID object.
        """
        if isinstance(session_id, str):
            session_uuid = uuid.UUID(session_id)
        else:
            session_uuid = session_id

        st.session_state["session_id"] = session_uuid
        st.query_params["session_id"] = str(session_uuid)
        return session_uuid

    @staticmethod
    def clear_session() -> None:
        """Clear the active session from state and remove query parameters."""
        if "session_id" in st.session_state:
            del st.session_state["session_id"]
        if "messages" in st.session_state:
            del st.session_state["messages"]
        if "session_id" in st.query_params:
            del st.query_params["session_id"]

    @classmethod
    def init_session(cls, api_client: Optional[APIClient] = None) -> uuid.UUID:
        """
        Ensure an active session exists.
        
        If a session ID is already stored in state or query params, returns it.
        Otherwise, requests a new session from the backend via api_client.create_session()
        (or generates a local UUID fallback) and synchronizes state.
        """
        existing = cls.get_session_id()
        if existing is not None:
            return existing

        if api_client is not None:
            new_id = api_client.create_session()
        else:
            new_id = uuid.uuid4()

        cls.set_session_id(new_id)
        return new_id

    @staticmethod
    def get_messages() -> list[dict[str, Any]]:
        """Retrieve conversation messages from Streamlit session state."""
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        return st.session_state["messages"]

    @classmethod
    def add_message(
        cls,
        role: str,
        content: str,
        action: Optional[str] = None,
        citations: Optional[list[Any]] = None,
    ) -> None:
        """Append a message to the current conversation state."""
        messages = cls.get_messages()
        messages.append({
            "role": role,
            "content": content,
            "action": action,
            "citations": citations or [],
        })
