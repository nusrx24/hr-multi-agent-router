"""
Sub-Agent stubs for the HR Multi-Agent Router.

Each sub-agent handles a specific HR domain. These are stub
implementations returning mock responses. In production, each
would integrate with real HR systems.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def scheduling_agent_node(state: AgentState) -> dict[str, Any]:
    """Handle scheduling requests (meetings, interviews, room bookings)."""
    request_text = state["request_text"].lower()
    user_id = state["user_id"]
    logger.info("SchedulingAgent processing for user=%s", user_id)

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%A, %B %d, %Y")

    if "interview" in request_text:
        response = (
            f"✅ **Interview Scheduled**\n\n"
            f"📅 Date: {tomorrow}\n🕐 Time: 2:00 PM - 3:00 PM\n"
            f"📍 Location: Conference Room B (or Virtual)\n"
            f"👥 Attendees: Hiring Manager, HR Representative\n\n"
            f"Calendar invites sent to all participants."
        )
    elif "room" in request_text or "conference" in request_text:
        response = (
            f"✅ **Room Booked**\n\n"
            f"📅 Date: {tomorrow}\n🕐 Time: 10:00 AM - 11:00 AM\n"
            f"📍 Room: Conference Room A (Building 2, Floor 3)\n"
            f"🖥️ Equipment: Projector, Whiteboard, Video Conferencing"
        )
    else:
        response = (
            f"✅ **Meeting Scheduled**\n\n"
            f"📅 Date: {tomorrow}\n🕐 Time: 10:00 AM - 10:30 AM\n"
            f"📍 Location: Virtual (Teams/Zoom link will be shared)\n"
            f"📋 Agenda: As per your request\n\n"
            f"Calendar invites sent. Reminder 15 min before."
        )

    return {"response": response}


async def leave_agent_node(state: AgentState) -> dict[str, Any]:
    """Handle leave requests (PTO, sick leave, vacation, balance checks)."""
    request_text = state["request_text"].lower()
    user_id = state["user_id"]
    logger.info("LeaveAgent processing for user=%s", user_id)

    if "balance" in request_text or "remaining" in request_text or "how many" in request_text:
        response = (
            f"📊 **Leave Balance Summary**\n\n"
            f"| Leave Type | Available | Used | Total |\n"
            f"|------------|-----------|------|-------|\n"
            f"| Vacation   | 12 days   | 3    | 15    |\n"
            f"| Sick Leave | 8 days    | 2    | 10    |\n"
            f"| Personal   | 3 days    | 0    | 3     |\n\n"
            f"Next accrual: 1st of next month (+1.25 days)."
        )
    elif "sick" in request_text:
        response = (
            f"✅ **Sick Leave Recorded**\n\n"
            f"📅 Date: Today\n📋 Type: Sick Leave\n"
            f"👤 Manager Notified: Yes (auto-notification)\n"
            f"📊 Remaining Sick Days: 7 of 10\n\n"
            f"No doctor's note needed for absences under 3 days."
        )
    elif "maternity" in request_text or "paternity" in request_text:
        lt = "Maternity" if "maternity" in request_text else "Paternity"
        wk = "16" if lt == "Maternity" else "4"
        response = (
            f"📋 **{lt} Leave Info**\n\n"
            f"⏱️ Duration: Up to {wk} weeks\n"
            f"📄 Required: Medical certificate, planned start date\n"
            f"⏰ Notice: At least 4 weeks before planned leave\n\n"
            f"Would you like to start the formal application?"
        )
    else:
        nxt = datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)
        response = (
            f"✅ **Leave Request Submitted**\n\n"
            f"📅 Date: {nxt.strftime('%A, %B %d, %Y')}\n"
            f"📋 Type: Paid Time Off (PTO)\n"
            f"👤 Approver: Your direct manager\n"
            f"⏳ Status: Pending Approval\n"
            f"📊 Remaining PTO after approval: 11 days"
        )

    return {"response": response}


async def compliance_agent_node(state: AgentState) -> dict[str, Any]:
    """Handle compliance and policy-related requests."""
    request_text = state["request_text"].lower()
    user_id = state["user_id"]
    logger.info("ComplianceAgent processing for user=%s", user_id)

    if "remote" in request_text or "work from home" in request_text:
        response = (
            f"📋 **Remote Work Policy**\n\n"
            f"• Eligible after 90-day probation\n"
            f"• Up to 3 remote days/week (hybrid)\n"
            f"• Core hours: 10 AM – 3 PM\n"
            f"• Submit request 48h in advance via HR portal\n\n"
            f"📄 Full policy: Handbook Section 4.2"
        )
    elif "harassment" in request_text or "discrimination" in request_text:
        response = (
            f"🔒 **Anti-Harassment Policy**\n\n"
            f"Zero-tolerance policy. Report via:\n"
            f"• 📧 hr@company.com\n"
            f"• 📞 Hotline: 1-800-XXX-XXXX\n"
            f"• 🌐 hr.company.com/report\n\n"
            f"All reports investigated within 48 hours.\n"
            f"📄 Full policy: Handbook Section 7.1"
        )
    else:
        response = (
            f"📋 **HR Policy Information**\n\n"
            f"Key policy areas:\n"
            f"• 📅 Attendance (Section 3.1)\n"
            f"• 🏖️ Leave & Time-Off (Section 4.1)\n"
            f"• 💻 Remote Work (Section 4.2)\n"
            f"• 🔒 Data Privacy (Section 6.1)\n"
            f"• ⚖️ Code of Conduct (Section 7.1)\n\n"
            f"Want me to look up a specific policy?"
        )

    return {"response": response}


async def clarification_agent_node(state: AgentState) -> dict[str, Any]:
    """Fallback agent for unclear or ambiguous requests."""
    error = state.get("error")
    user_id = state["user_id"]
    confidence = state.get("confidence", 0.0)
    logger.info("ClarificationAgent for user=%s (confidence=%.2f)", user_id, confidence)

    if error:
        response = (
            f"🤔 **I apologize for the inconvenience**\n\n"
            f"I encountered a temporary issue. Please try again, or "
            f"contact HR directly at hr@company.com / ext. 2500.\n\n"
            f"I can help with:\n"
            f"• 📅 Scheduling — meetings, interviews\n"
            f"• 🏖️ Leave — PTO, sick leave\n"
            f"• 📋 Compliance — policies, regulations"
        )
    else:
        response = (
            f"🤔 **Could you clarify your request?**\n\n"
            f"Examples of what I can help with:\n\n"
            f"📅 **Scheduling:** _\"Schedule a meeting for tomorrow at 2pm\"_\n"
            f"🏖️ **Leave:** _\"I'd like to request PTO for next Monday\"_\n"
            f"📋 **Compliance:** _\"What is the remote work policy?\"_\n\n"
            f"Could you rephrase with more detail?"
        )

    return {"response": response}
