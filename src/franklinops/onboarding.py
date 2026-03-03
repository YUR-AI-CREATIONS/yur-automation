from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit import AuditLogger
from .opsdb import OpsDB
from .settings import FranklinOpsSettings


class OnboardingOrchestrator:
    """
    Intelligent onboarding system that guides users through setup and first automations.
    
    Features:
    - Business type detection and tailored setup
    - Progressive feature introduction
    - Smart configuration assistance  
    - Success tracking and celebration
    """
    
    def __init__(self, db: OpsDB, audit: AuditLogger, settings: FranklinOpsSettings):
        self.db = db
        self.audit = audit
        self.settings = settings
        self._ensure_onboarding_tables()
    
    def _ensure_onboarding_tables(self):
        """Create onboarding tracking tables if they don't exist."""
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_state (
                user_id TEXT PRIMARY KEY DEFAULT 'default',
                current_step TEXT NOT NULL DEFAULT 'welcome',
                business_type TEXT DEFAULT '',
                setup_progress TEXT DEFAULT '{}',
                completed_steps TEXT DEFAULT '[]',
                preferences TEXT DEFAULT '{}',
                first_login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                onboarding_completed BOOLEAN DEFAULT FALSE
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                achievement_type TEXT NOT NULL,
                achievement_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.commit()
    
    def get_onboarding_state(self, user_id: str = "default") -> Dict[str, Any]:
        """Get current onboarding state for a user."""
        row = self.db.conn.execute(
            "SELECT * FROM onboarding_state WHERE user_id = ?", 
            (user_id,)
        ).fetchone()
        
        if not row:
            # Create initial state
            self.db.conn.execute("""
                INSERT INTO onboarding_state (user_id, current_step, setup_progress, completed_steps, preferences)
                VALUES (?, 'welcome', '{}', '[]', '{}')
            """, (user_id,))
            self.db.conn.commit()
            return self.get_onboarding_state(user_id)
        
        return {
            "user_id": row[0],
            "current_step": row[1],
            "business_type": row[2] or "",
            "setup_progress": json.loads(row[3] or "{}"),
            "completed_steps": json.loads(row[4] or "[]"),
            "preferences": json.loads(row[5] or "{}"),
            "first_login_at": row[6],
            "last_activity_at": row[7],
            "onboarding_completed": bool(row[8])
        }
    
    def update_onboarding_state(
        self, 
        user_id: str = "default",
        **updates
    ) -> Dict[str, Any]:
        """Update onboarding state."""
        current = self.get_onboarding_state(user_id)
        
        # Build update query dynamically
        update_fields = []
        update_values = []
        
        for field, value in updates.items():
            if field in ["setup_progress", "completed_steps", "preferences"] and isinstance(value, (dict, list)):
                value = json.dumps(value)
            update_fields.append(f"{field} = ?")
            update_values.append(value)
        
        update_fields.append("last_activity_at = CURRENT_TIMESTAMP")
        update_values.append(user_id)
        
        query = f"UPDATE onboarding_state SET {', '.join(update_fields)} WHERE user_id = ?"
        self.db.conn.execute(query, update_values)
        self.db.conn.commit()
        
        self.audit.append(
            actor=f"user:{user_id}",
            action="onboarding_state_updated",
            scope="internal",
            details={"updates": updates}
        )
        
        return self.get_onboarding_state(user_id)
    
    def detect_business_type(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligently detect business type from user input."""
        business_indicators = {
            "construction": [
                "construction", "contractor", "builder", "concrete", "electrical", 
                "plumbing", "roofing", "hvac", "excavation", "foundation", "framing"
            ],
            "professional_services": [
                "consulting", "legal", "accounting", "marketing", "design", "agency",
                "professional", "services", "freelance", "coaching"
            ],
            "retail": [
                "store", "shop", "retail", "sales", "products", "inventory", 
                "customers", "e-commerce", "merchandise"
            ],
            "manufacturing": [
                "manufacturing", "factory", "production", "assembly", "parts",
                "equipment", "industrial", "supply chain"
            ]
        }
        
        user_text = " ".join([
            user_input.get("business_description", ""),
            user_input.get("industry", ""),
            user_input.get("company_name", ""),
            user_input.get("role", "")
        ]).lower()
        
        scores = {}
        for business_type, keywords in business_indicators.items():
            score = sum(1 for keyword in keywords if keyword in user_text)
            if score > 0:
                scores[business_type] = score
        
        detected_type = max(scores, key=scores.get) if scores else "general"
        confidence = scores.get(detected_type, 0) / max(len(business_indicators[detected_type]), 1)
        
        return {
            "detected_type": detected_type,
            "confidence": confidence,
            "all_scores": scores,
            "suggestions": self._get_business_type_suggestions(detected_type)
        }
    
    def _get_business_type_suggestions(self, business_type: str) -> Dict[str, Any]:
        """Get tailored suggestions based on business type."""
        suggestions = {
            "construction": {
                "priority_features": ["project_management", "invoice_tracking", "cashflow_forecasting"],
                "folder_structure": ["Projects", "Bidding", "Invoices", "Submittals"],
                "automation_opportunities": [
                    "Bidding deadline tracking",
                    "Invoice approval workflow", 
                    "Payment reminder automation",
                    "Project document organization"
                ],
                "quick_wins": [
                    "Set up automatic bid due date reminders",
                    "Organize project documents by job number",
                    "Track invoice payment status"
                ]
            },
            "professional_services": {
                "priority_features": ["client_management", "time_tracking", "invoice_automation"],
                "folder_structure": ["Clients", "Projects", "Invoices", "Proposals"],
                "automation_opportunities": [
                    "Client communication tracking",
                    "Proposal follow-up automation",
                    "Time tracking and billing",
                    "Client onboarding workflows"
                ],
                "quick_wins": [
                    "Set up client follow-up reminders",
                    "Automate invoice generation",
                    "Track project deadlines"
                ]
            },
            "general": {
                "priority_features": ["document_organization", "task_management", "basic_automation"],
                "folder_structure": ["Documents", "Projects", "Finance", "Contacts"],
                "automation_opportunities": [
                    "Document organization",
                    "Task reminder system",
                    "Basic workflow automation",
                    "Contact management"
                ],
                "quick_wins": [
                    "Organize important documents",
                    "Set up task reminders",
                    "Create contact database"
                ]
            }
        }
        
        return suggestions.get(business_type, suggestions["general"])
    
    def generate_setup_plan(self, user_id: str = "default") -> Dict[str, Any]:
        """Generate a personalized setup plan based on detected business type."""
        state = self.get_onboarding_state(user_id)
        business_type = state.get("business_type", "general")
        suggestions = self._get_business_type_suggestions(business_type)
        
        setup_steps = [
            {
                "id": "folder_detection",
                "title": "📁 Connect Your Files",
                "description": "Let's find your business documents automatically",
                "estimated_time": "2 minutes",
                "priority": "high",
                "completed": "folder_detection" in state.get("completed_steps", [])
            },
            {
                "id": "first_automation", 
                "title": "⚡ Your First Automation",
                "description": f"Set up: {suggestions['quick_wins'][0]}",
                "estimated_time": "3 minutes",
                "priority": "high",
                "completed": "first_automation" in state.get("completed_steps", [])
            },
            {
                "id": "notification_preferences",
                "title": "🔔 Smart Notifications",
                "description": "Configure how I'll keep you informed",
                "estimated_time": "1 minute", 
                "priority": "medium",
                "completed": "notification_preferences" in state.get("completed_steps", [])
            },
            {
                "id": "advanced_features",
                "title": "🚀 Power User Features",
                "description": "Unlock advanced automation capabilities",
                "estimated_time": "5 minutes",
                "priority": "low",
                "completed": "advanced_features" in state.get("completed_steps", [])
            }
        ]
        
        return {
            "business_type": business_type,
            "setup_steps": setup_steps,
            "suggestions": suggestions,
            "progress_percentage": len(state.get("completed_steps", [])) / len(setup_steps) * 100,
            "next_step": next((step for step in setup_steps if not step["completed"]), None)
        }
    
    def auto_detect_folders(self) -> Dict[str, Any]:
        """Automatically detect likely business folder locations."""
        common_paths = [
            Path.home() / "OneDrive",
            Path.home() / "OneDrive - Personal", 
            Path.home() / "OneDrive - Business",
            Path.home() / "Documents",
            Path.home() / "Desktop",
        ]
        
        detected_folders = {}
        
        for base_path in common_paths:
            if base_path.exists():
                for subfolder in base_path.iterdir():
                    if subfolder.is_dir():
                        folder_name = subfolder.name.lower()
                        
                        # Detect project folders
                        if any(keyword in folder_name for keyword in ["project", "job", "work", "client"]):
                            if "projects" not in detected_folders:
                                detected_folders["projects"] = str(subfolder)
                        
                        # Detect bidding/sales folders
                        elif any(keyword in folder_name for keyword in ["bid", "quote", "proposal", "estimate", "sales"]):
                            if "bidding" not in detected_folders:
                                detected_folders["bidding"] = str(subfolder)
                        
                        # Detect invoice/finance folders
                        elif any(keyword in folder_name for keyword in ["invoice", "bill", "finance", "accounting", "money"]):
                            if "finance" not in detected_folders:
                                detected_folders["finance"] = str(subfolder)
        
        return {
            "detected_folders": detected_folders,
            "confidence": "high" if len(detected_folders) >= 2 else "medium" if detected_folders else "low",
            "suggestions": [
                "✅ I found folders that look like business documents!",
                "📁 Would you like me to monitor these for new files?", 
                "⚡ I can automatically organize and process documents as they arrive."
            ] if detected_folders else [
                "🤔 I couldn't find obvious business folders automatically.",
                "📂 No worries! You can point me to your folders manually.",
                "💡 Tip: Organizing files in clear folders helps me help you better."
            ]
        }
    
    def record_achievement(self, user_id: str = "default", achievement_type: str = "", achievement_data: Dict = None):
        """Record a user achievement for celebration and progress tracking."""
        self.db.conn.execute("""
            INSERT INTO onboarding_achievements (user_id, achievement_type, achievement_data)
            VALUES (?, ?, ?)
        """, (user_id, achievement_type, json.dumps(achievement_data or {})))
        self.db.conn.commit()
        
        self.audit.append(
            actor=f"user:{user_id}",
            action="achievement_unlocked",
            scope="internal",
            details={"type": achievement_type, "data": achievement_data}
        )
    
    def get_onboarding_progress(self, user_id: str = "default") -> Dict[str, Any]:
        """Get comprehensive onboarding progress and next steps."""
        state = self.get_onboarding_state(user_id)
        plan = self.generate_setup_plan(user_id)
        
        # Get recent achievements
        achievements = self.db.conn.execute("""
            SELECT achievement_type, achievement_data, created_at 
            FROM onboarding_achievements 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 5
        """, (user_id,)).fetchall()
        
        return {
            "state": state,
            "plan": plan,
            "achievements": [
                {
                    "type": row[0],
                    "data": json.loads(row[1] or "{}"),
                    "created_at": row[2]
                } for row in achievements
            ],
            "is_new_user": len(state.get("completed_steps", [])) == 0,
            "needs_attention": not state.get("onboarding_completed", False) and 
                             len(state.get("completed_steps", [])) > 0
        }


def create_welcome_message(business_type: str = "general", user_name: str = "") -> Dict[str, Any]:
    """Create a personalized welcome message based on business context."""
    
    business_greetings = {
        "construction": f"""
🏗️ **Welcome to FranklinOps, {user_name or 'Constructor'}!**

I'm your dedicated business intelligence assistant, specially designed for construction and contracting operations. 

**I can help you:**
• 📋 Track bidding deadlines automatically
• 💰 Monitor project cashflow and payments  
• 📄 Organize project documents intelligently
• ⚡ Automate invoice approvals and reminders
• 📊 Generate insights from your business data

**Let's get started!** I'll have you up and running with your first automation in under 5 minutes.
        """,
        "professional_services": f"""
💼 **Welcome to FranklinOps, {user_name or 'Professional'}!**

I'm your AI business assistant, designed to streamline professional service operations.

**I can help you:**
• 👥 Manage client relationships and follow-ups
• 📈 Track project progress and deadlines
• 💸 Automate invoicing and payment tracking
• 📧 Handle client communication workflows
• 📊 Provide insights on business performance

**Ready to save hours every week?** Let's set up your first automation together!
        """,
        "general": f"""
🚀 **Welcome to FranklinOps, {user_name or 'there'}!**

I'm your intelligent business automation assistant, ready to eliminate tedious work and boost your productivity.

**I can help you:**
• 📁 Organize and search all your documents
• ⚡ Automate repetitive business tasks
• 📋 Track important deadlines and follow-ups  
• 💡 Provide insights from your business data
• 🎯 Suggest optimizations to save time and money

**Let's transform how you work!** I'll guide you through setting up your first time-saving automation.
        """
    }
    
    return {
        "message": business_greetings.get(business_type, business_greetings["general"]).strip(),
        "next_steps": [
            "🔍 Let me detect your business folders automatically",
            "⚡ Choose your first automation to set up", 
            "🎯 Start saving time immediately"
        ],
        "estimated_setup_time": "5 minutes"
    }