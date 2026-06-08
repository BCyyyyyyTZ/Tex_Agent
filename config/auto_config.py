"""
Auto 模式标识（行为与提示词见 config/context_profiles.py → PROFILES["auto_single"]）。
"""
from config.context_settings import PROFILE_AUTO_SINGLE, get_profile_agent_spec

AUTO_WORKFLOW_LABEL = "auto_single"
AUTO_NODE_ID = str(get_profile_agent_spec(PROFILE_AUTO_SINGLE).get("node_id") or "auto_response")
