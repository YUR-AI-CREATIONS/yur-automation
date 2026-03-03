from __future__ import annotations

from typing import Any, Dict, List


def generate_conversational_welcome(user_context: Dict[str, Any]) -> str:
    """Generate a conversational welcome message based on user context."""
    
    # Extract context information
    pending_approvals = user_context.get("pending_approvals", 0)
    overdue_tasks = user_context.get("overdue_tasks", 0)
    new_notifications = user_context.get("new_notifications", 0)
    recent_automations = user_context.get("recent_automations", 0)
    time_of_day = user_context.get("time_of_day", "day")
    
    # Generate greeting based on time
    greeting_map = {
        "morning": "Good morning",
        "afternoon": "Good afternoon", 
        "evening": "Good evening",
        "day": "Hello"
    }
    greeting = greeting_map.get(time_of_day, "Hello")
    
    # Build conversational message
    message_parts = [f"{greeting}! "]
    
    # Add context-aware updates
    if recent_automations > 0:
        message_parts.append(f"I automated {recent_automations} tasks for you recently. ")
    
    if pending_approvals > 0:
        message_parts.append(f"You have {pending_approvals} item{'s' if pending_approvals > 1 else ''} awaiting approval. ")
    
    if overdue_tasks > 0:
        message_parts.append(f"{overdue_tasks} task{'s are' if overdue_tasks > 1 else ' is'} overdue and need{'s' if overdue_tasks == 1 else ''} attention. ")
    
    if new_notifications > 0:
        message_parts.append(f"I have {new_notifications} new update{'s' if new_notifications > 1 else ''} for you. ")
    
    # Add encouraging close if no urgent items
    if pending_approvals == 0 and overdue_tasks == 0:
        message_parts.append("Everything looks good! What would you like to work on today?")
    else:
        message_parts.append("What would you like to tackle first?")
    
    return "".join(message_parts)


def generate_smart_suggestions(user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate contextual action suggestions."""
    
    suggestions = []
    
    # Priority-based suggestions
    if user_context.get("pending_approvals", 0) > 0:
        suggestions.append({
            "text": f"Review {user_context['pending_approvals']} pending approval{'s' if user_context['pending_approvals'] > 1 else ''}",
            "action": "show_approvals",
            "priority": "high",
            "icon": "⏳"
        })
    
    if user_context.get("overdue_tasks", 0) > 0:
        suggestions.append({
            "text": f"Update {user_context['overdue_tasks']} overdue task{'s' if user_context['overdue_tasks'] > 1 else ''}",
            "action": "show_overdue_tasks", 
            "priority": "high",
            "icon": "🚨"
        })
    
    if user_context.get("new_leads", 0) > 0:
        suggestions.append({
            "text": f"Follow up on {user_context['new_leads']} new lead{'s' if user_context['new_leads'] > 1 else ''}",
            "action": "show_new_leads",
            "priority": "medium",
            "icon": "🎯"
        })
    
    # Always available helpful suggestions
    suggestions.extend([
        {
            "text": "Ask me anything about your business",
            "action": "open_chat",
            "priority": "low",
            "icon": "💬"
        },
        {
            "text": "Run automation scan",
            "action": "run_pilot",
            "priority": "low", 
            "icon": "⚡"
        },
        {
            "text": "View business insights",
            "action": "show_metrics",
            "priority": "low",
            "icon": "📊"
        }
    ])
    
    # Sort by priority and limit
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: priority_order.get(x["priority"], 2))
    
    return suggestions[:6]  # Limit to 6 suggestions


def generate_conversational_chat_response(user_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a conversational response structure for the chat interface."""
    
    # Common business question patterns
    quick_responses = {
        "status": {
            "triggers": ["how", "status", "doing", "going"],
            "response": "Here's how things are looking:",
            "show_dashboard": True
        },
        "help": {
            "triggers": ["help", "what can", "how do", "show me"],
            "response": "I can help you with several things:",
            "show_suggestions": True
        },
        "problems": {
            "triggers": ["problem", "issue", "error", "wrong"],
            "response": "Let me check what might need attention:",
            "show_issues": True
        },
        "money": {
            "triggers": ["money", "cash", "invoice", "payment", "owe", "paid"],
            "response": "Here's your financial situation:",
            "show_finance": True
        },
        "leads": {
            "triggers": ["lead", "customer", "client", "prospect", "sales"],
            "response": "Here's what's happening with your sales:",
            "show_sales": True
        }
    }
    
    user_lower = user_message.lower()
    response_type = "general"
    
    # Detect response type
    for response_key, config in quick_responses.items():
        if any(trigger in user_lower for trigger in config["triggers"]):
            response_type = response_key
            break
    
    if response_type in quick_responses:
        config = quick_responses[response_type]
        return {
            "response_type": "quick",
            "message": config["response"],
            "show_dashboard": config.get("show_dashboard", False),
            "show_suggestions": config.get("show_suggestions", False),
            "show_issues": config.get("show_issues", False),
            "show_finance": config.get("show_finance", False),
            "show_sales": config.get("show_sales", False),
            "conversational": True
        }
    else:
        return {
            "response_type": "search",
            "message": "Let me search through your business data...",
            "needs_ai_response": True,
            "conversational": True
        }


def generate_contextual_help(current_page: str, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate contextual help based on current page and user situation."""
    
    help_items = []
    
    page_help = {
        "dashboard": [
            {
                "title": "What's the Today Queue?",
                "description": "Items that need your attention today - approvals, overdue tasks, and important updates.",
                "action": "explain_today_queue"
            },
            {
                "title": "How do I increase automation?",
                "description": "Adjust autonomy levels to let me handle more tasks automatically.",
                "action": "show_autonomy_settings"
            }
        ],
        "ops": [
            {
                "title": "How to search my documents?",
                "description": "Ask questions like 'Which invoices are unpaid?' or 'Show me the Johnson project files'.",
                "action": "show_search_examples"
            },
            {
                "title": "Setting up folder monitoring",
                "description": "Connect your OneDrive folders so I can automatically organize and process new files.",
                "action": "configure_folders"
            }
        ],
        "sales": [
            {
                "title": "Automating lead follow-up",
                "description": "I can automatically create follow-up tasks and draft outreach emails for new leads.",
                "action": "setup_sales_automation"
            },
            {
                "title": "Email sequences",
                "description": "Set up automated email sequences for different types of prospects.",
                "action": "setup_email_sequences"
            }
        ],
        "finance": [
            {
                "title": "Invoice approval workflow",
                "description": "I can automatically detect new invoices and route them for approval based on your rules.",
                "action": "setup_ap_automation"
            },
            {
                "title": "Cash flow monitoring",
                "description": "Upload your cash flow spreadsheets and I'll alert you to potential shortages.",
                "action": "setup_cashflow_monitoring"
            }
        ]
    }
    
    # Get page-specific help
    help_items.extend(page_help.get(current_page, []))
    
    # Add context-specific help
    if user_context.get("pending_approvals", 0) > 0:
        help_items.append({
            "title": "Quick approval tips",
            "description": "You can approve multiple similar items at once, or set up auto-approval rules.",
            "action": "show_approval_tips"
        })
    
    if user_context.get("setup_incomplete", False):
        help_items.append({
            "title": "Complete your setup",
            "description": "Finish connecting your folders and preferences to unlock full automation.",
            "action": "resume_onboarding"
        })
    
    return help_items[:4]  # Limit to most relevant items


def format_business_insight(data_type: str, data: Dict[str, Any]) -> str:
    """Format business data into conversational insights."""
    
    formatters = {
        "cashflow": lambda d: f"Your cash flow shows ${d.get('balance', 0):,.2f} current balance with ${d.get('projected_shortage', 0):,.2f} potential shortage in {d.get('shortage_weeks', 0)} weeks." if d.get('projected_shortage', 0) > 0 else f"Your cash flow looks healthy with ${d.get('balance', 0):,.2f} current balance.",
        
        "sales": lambda d: f"You have {d.get('active_leads', 0)} active leads, {d.get('recent_opportunities', 0)} opportunities this month, and {d.get('conversion_rate', 0):.1f}% conversion rate.",
        
        "projects": lambda d: f"You're managing {d.get('active_projects', 0)} active projects, with {d.get('overdue_tasks', 0)} overdue tasks across all projects." if d.get('overdue_tasks', 0) > 0 else f"You're managing {d.get('active_projects', 0)} active projects, all on track.",
        
        "finance": lambda d: f"You have ${d.get('unpaid_invoices', 0):,.2f} in unpaid invoices ({d.get('unpaid_count', 0)} invoices), with {d.get('aging_30_plus', 0)} invoices over 30 days old.",
        
        "automation": lambda d: f"I've automated {d.get('automated_actions', 0)} tasks this month, saving you approximately {d.get('time_saved_hours', 0):.1f} hours."
    }
    
    formatter = formatters.get(data_type, lambda d: str(d))
    return formatter(data)


def generate_onboarding_prompt(step: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate conversational onboarding prompts."""
    
    prompts = {
        "welcome": {
            "title": "Welcome! Let's get you set up in 5 minutes",
            "message": "I'm your business automation assistant. I'll help you organize documents, track deadlines, and automate routine tasks. Ready to start?",
            "primary_action": {"text": "Let's do it!", "action": "start_onboarding"},
            "secondary_action": {"text": "Tell me more", "action": "show_features"}
        },
        "business_type": {
            "title": "Tell me about your business",
            "message": "This helps me tailor the setup to your specific needs. What type of work do you do?",
            "primary_action": {"text": "Construction/Contracting", "action": "set_business_type", "value": "construction"},
            "secondary_action": {"text": "Other", "action": "custom_business_type"}
        },
        "folder_detection": {
            "title": "Let's find your business files",
            "message": "I'll scan your computer for business folders like Projects, Bidding, or Invoices. This lets me organize and search your documents automatically.",
            "primary_action": {"text": "Auto-detect folders", "action": "detect_folders"},
            "secondary_action": {"text": "I'll set them up manually", "action": "manual_folder_setup"}
        },
        "first_automation": {
            "title": "Choose your first automation",
            "message": "What would save you the most time right now?",
            "primary_action": {"text": "Organize project documents", "action": "setup_document_automation"},
            "secondary_action": {"text": "Track bidding deadlines", "action": "setup_deadline_tracking"}
        }
    }
    
    return prompts.get(step, {
        "title": "Next step",
        "message": "Ready to continue?", 
        "primary_action": {"text": "Continue", "action": "continue_onboarding"}
    })