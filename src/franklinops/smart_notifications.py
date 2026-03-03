from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .audit import AuditLogger
from .opsdb import OpsDB
from .settings import FranklinOpsSettings


class SmartNotificationSystem:
    """
    Intelligent notification system that provides contextual, actionable notifications.
    
    Features:
    - Smart timing based on user activity patterns
    - Contextual notifications based on business events
    - Actionable suggestions with one-click responses
    - Notification preferences and filtering
    """
    
    def __init__(self, db: OpsDB, audit: AuditLogger, settings: FranklinOpsSettings):
        self.db = db
        self.audit = audit
        self.settings = settings
        self._ensure_notification_tables()
    
    def _ensure_notification_tables(self):
        """Create notification system tables."""
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                action_data TEXT DEFAULT '{}',
                priority INTEGER DEFAULT 3,
                read_at TIMESTAMP NULL,
                clicked_at TIMESTAMP NULL,
                dismissed_at TIMESTAMP NULL,
                expires_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY DEFAULT 'default',
                categories_enabled TEXT DEFAULT '[]',
                min_priority INTEGER DEFAULT 2,
                smart_timing BOOLEAN DEFAULT TRUE,
                daily_digest BOOLEAN DEFAULT TRUE,
                preferences_data TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_templates (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title_template TEXT NOT NULL,
                message_template TEXT NOT NULL,
                action_template TEXT DEFAULT '{}',
                priority INTEGER DEFAULT 3,
                expires_minutes INTEGER DEFAULT 1440,
                active BOOLEAN DEFAULT TRUE
            )
        """)
        
        self.db.conn.commit()
        self._seed_notification_templates()
    
    def _seed_notification_templates(self):
        """Seed initial notification templates."""
        templates = [
            {
                "id": "approval_pending",
                "category": "approvals",
                "title": "⏳ {count} approval{s} awaiting your decision",
                "message": "You have {items} pending approval. Review and decide to keep workflows moving.",
                "action": {"type": "show_approvals", "params": {}},
                "priority": 4
            },
            {
                "id": "overdue_tasks",
                "category": "tasks",
                "title": "🚨 {count} overdue task{s}",
                "message": "{items} past their due date. Update status or reschedule to stay on track.",
                "action": {"type": "show_overdue_tasks", "params": {}},
                "priority": 5
            },
            {
                "id": "new_leads",
                "category": "sales",
                "title": "🎯 {count} new lead{s} captured",
                "message": "I found {items} in your bidding folder. Create follow-up tasks to convert them!",
                "action": {"type": "show_new_leads", "params": {}},
                "priority": 3
            },
            {
                "id": "cashflow_alert",
                "category": "finance",
                "title": "💰 Cash flow attention needed",
                "message": "Upcoming cash shortage detected. Review {items} or send payment reminders.",
                "action": {"type": "show_cashflow", "params": {}},
                "priority": 4
            },
            {
                "id": "success_milestone",
                "category": "success",
                "title": "🎉 Milestone achieved!",
                "message": "{message} Keep up the great work!",
                "action": {"type": "show_metrics", "params": {}},
                "priority": 2
            },
            {
                "id": "optimization_tip",
                "category": "optimization",
                "title": "💡 {title}",
                "message": "{message} This could save you time and improve efficiency.",
                "action": {"type": "show_suggestions", "params": {}},
                "priority": 2
            },
            {
                "id": "system_issue",
                "category": "system",
                "title": "⚠️ {title}",
                "message": "{message} Click to resolve this issue.",
                "action": {"type": "show_issues", "params": {}},
                "priority": 4
            }
        ]
        
        for template in templates:
            # Check if template already exists
            exists = self.db.conn.execute(
                "SELECT 1 FROM notification_templates WHERE id = ?", 
                (template["id"],)
            ).fetchone()
            
            if not exists:
                self.db.conn.execute("""
                    INSERT INTO notification_templates 
                    (id, category, title_template, message_template, action_template, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    template["id"],
                    template["category"],
                    template["title"],
                    template["message"],
                    json.dumps(template["action"]),
                    template["priority"]
                ))
        
        self.db.conn.commit()
    
    def generate_smart_notifications(self, user_id: str = "default") -> Dict[str, Any]:
        """Generate smart notifications based on current business state."""
        notifications_created = []
        
        # Check for pending approvals
        pending_approvals = self._check_pending_approvals()
        if pending_approvals:
            notification = self._create_notification_from_template(
                "approval_pending",
                user_id,
                {
                    "count": pending_approvals["count"],
                    "s": "s" if pending_approvals["count"] > 1 else "",
                    "items": pending_approvals["description"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        # Check for overdue tasks
        overdue_tasks = self._check_overdue_tasks()
        if overdue_tasks:
            notification = self._create_notification_from_template(
                "overdue_tasks",
                user_id,
                {
                    "count": overdue_tasks["count"],
                    "s": "s" if overdue_tasks["count"] > 1 else "",
                    "items": overdue_tasks["description"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        # Check for new leads
        new_leads = self._check_new_leads()
        if new_leads:
            notification = self._create_notification_from_template(
                "new_leads",
                user_id,
                {
                    "count": new_leads["count"],
                    "s": "s" if new_leads["count"] > 1 else "",
                    "items": new_leads["description"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        # Check for cashflow issues
        cashflow_issues = self._check_cashflow_issues()
        if cashflow_issues:
            notification = self._create_notification_from_template(
                "cashflow_alert",
                user_id,
                {
                    "items": cashflow_issues["description"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        # Check for success milestones
        success_milestones = self._check_success_milestones()
        if success_milestones:
            notification = self._create_notification_from_template(
                "success_milestone",
                user_id,
                {
                    "message": success_milestones["message"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        # Check for optimization opportunities
        optimization_tips = self._check_optimization_opportunities()
        if optimization_tips:
            notification = self._create_notification_from_template(
                "optimization_tip",
                user_id,
                {
                    "title": optimization_tips["title"],
                    "message": optimization_tips["message"]
                }
            )
            if notification:
                notifications_created.append(notification)
        
        return {
            "notifications_created": len(notifications_created),
            "notifications": notifications_created
        }
    
    def _check_pending_approvals(self) -> Optional[Dict[str, Any]]:
        """Check for pending approvals requiring attention."""
        pending = self.db.execute("""
            SELECT COUNT(*) as count, 
                   GROUP_CONCAT(workflow || ' - ' || intent, ', ') as items
            FROM approval 
            WHERE status = 'pending'
            AND created_at > datetime('now', '-24 hours')
        """).fetchone()
        
        if pending and pending[0] > 0:
            return {
                "count": pending[0],
                "description": pending[1] or "Various items"
            }
        return None
    
    def _check_overdue_tasks(self) -> Optional[Dict[str, Any]]:
        """Check for overdue tasks."""
        overdue = self.db.execute("""
            SELECT COUNT(*) as count,
                   GROUP_CONCAT(SUBSTR(title, 1, 30) || '...', ', ') as items
            FROM task 
            WHERE status != 'completed'
            AND due_date < date('now')
            LIMIT 5
        """).fetchone()
        
        if overdue and overdue[0] > 0:
            return {
                "count": overdue[0],
                "description": overdue[1] or "Various tasks"
            }
        return None
    
    def _check_new_leads(self) -> Optional[Dict[str, Any]]:
        """Check for new leads captured."""
        new_leads = self.db.execute("""
            SELECT COUNT(*) as count,
                   GROUP_CONCAT(SUBSTR(company || ' - ' || contact_name, 1, 40), ', ') as items
            FROM sales_lead 
            WHERE created_at > datetime('now', '-24 hours')
            AND status = 'active'
        """).fetchone()
        
        if new_leads and new_leads[0] > 0:
            return {
                "count": new_leads[0],
                "description": new_leads[1] or "New opportunities"
            }
        return None
    
    def _check_cashflow_issues(self) -> Optional[Dict[str, Any]]:
        """Check for potential cashflow issues."""
        # Check for invoices unpaid > 30 days
        aging_invoices = self.db.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM invoice 
            WHERE status != 'paid'
            AND created_at < datetime('now', '-30 days')
        """).fetchone()
        
        if aging_invoices and aging_invoices[0] > 2:
            return {
                "description": f"{aging_invoices[0]} invoices totaling ${aging_invoices[1]:,.2f} are 30+ days overdue"
            }
        
        # Check for upcoming negative cashflow
        negative_weeks = self.db.execute("""
            SELECT COUNT(*) as weeks
            FROM cashflow_line 
            WHERE amount < -1000
            AND week_date > date('now')
            AND week_date < date('now', '+4 weeks')
        """).fetchone()
        
        if negative_weeks and negative_weeks[0] > 0:
            return {
                "description": f"{negative_weeks[0]} weeks show potential cash shortages"
            }
        
        return None
    
    def _check_success_milestones(self) -> Optional[Dict[str, Any]]:
        """Check for success milestones worth celebrating."""
        # Check for automation milestones
        automated_today = self.db.execute("""
            SELECT COUNT(*) as count
            FROM audit_event 
            WHERE actor LIKE 'system%'
            AND created_at > datetime('now', '-24 hours')
            AND action NOT IN ('audit_event_created', 'system_startup', 'system_shutdown')
        """).fetchone()
        
        if automated_today and automated_today[0] > 20:
            return {
                "message": f"I automated {automated_today[0]} tasks for you today! That's roughly {automated_today[0] * 3} minutes saved."
            }
        
        # Check for completed projects
        completed_projects = self.db.execute("""
            SELECT COUNT(*) as count
            FROM project 
            WHERE status = 'completed'
            AND updated_at > datetime('now', '-7 days')
        """).fetchone()
        
        if completed_projects and completed_projects[0] > 0:
            return {
                "message": f"Congratulations on completing {completed_projects[0]} project{'s' if completed_projects[0] > 1 else ''} this week!"
            }
        
        return None
    
    def _check_optimization_opportunities(self) -> Optional[Dict[str, Any]]:
        """Check for optimization opportunities."""
        # Check for repetitive manual actions
        manual_actions = self.db.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_event 
            WHERE actor = 'human'
            AND created_at > datetime('now', '-7 days')
            GROUP BY action
            HAVING count > 5
            ORDER BY count DESC
            LIMIT 1
        """).fetchone()
        
        if manual_actions:
            action_name = manual_actions[0].replace('_', ' ').title()
            return {
                "title": f"Automate {action_name}?",
                "message": f"You've done '{action_name}' {manual_actions[1]} times this week. I could automate this for you!"
            }
        
        # Check for email draft backlog
        email_drafts = self.db.execute("""
            SELECT COUNT(*) as count
            FROM outbound_message 
            WHERE status = 'draft'
            AND created_at < datetime('now', '-3 days')
        """).fetchone()
        
        if email_drafts and email_drafts[0] > 3:
            return {
                "title": "Email workflow optimization",
                "message": f"You have {email_drafts[0]} email drafts sitting for 3+ days. Consider enabling auto-send for routine communications."
            }
        
        return None
    
    def _create_notification_from_template(
        self, 
        template_id: str, 
        user_id: str, 
        variables: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a notification from a template."""
        template = self.db.execute("""
            SELECT category, title_template, message_template, action_template, priority, expires_minutes
            FROM notification_templates 
            WHERE id = ? AND active = TRUE
        """, (template_id,)).fetchone()
        
        if not template:
            return None
        
        category, title_template, message_template, action_template, priority, expires_minutes = template
        
        # Check if similar notification already exists (avoid spam)
        existing = self.db.execute("""
            SELECT 1 FROM notifications 
            WHERE user_id = ? AND type = ? AND category = ?
            AND dismissed_at IS NULL AND expires_at > datetime('now')
            AND created_at > datetime('now', '-1 hours')
        """, (user_id, template_id, category)).fetchone()
        
        if existing:
            return None  # Don't create duplicate notifications
        
        # Format templates with variables
        try:
            title = title_template.format(**variables)
            message = message_template.format(**variables)
            action_data = json.loads(action_template)
        except (KeyError, json.JSONDecodeError) as e:
            # Template formatting failed, skip this notification
            return None
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        
        # Create notification
        notification_id = self.db.execute("""
            INSERT INTO notifications (user_id, type, category, title, message, action_data, priority, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, template_id, category, title, message, 
            json.dumps(action_data), priority, expires_at.isoformat()
        )).lastrowid
        
        self.db.conn.commit()
        
        return {
            "id": notification_id,
            "type": template_id,
            "category": category,
            "title": title,
            "message": message,
            "action_data": action_data,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def get_active_notifications(self, user_id: str = "default", limit: int = 20) -> List[Dict[str, Any]]:
        """Get active notifications for a user."""
        rows = self.db.execute("""
            SELECT id, type, category, title, message, action_data, priority, 
                   read_at, clicked_at, dismissed_at, created_at
            FROM notifications 
            WHERE user_id = ?
            AND dismissed_at IS NULL
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        
        return [
            {
                "id": row[0],
                "type": row[1],
                "category": row[2],
                "title": row[3],
                "message": row[4],
                "action_data": json.loads(row[5] or "{}"),
                "priority": row[6],
                "read": bool(row[7]),
                "clicked": bool(row[8]),
                "dismissed": bool(row[9]),
                "created_at": row[10]
            }
            for row in rows
        ]
    
    def mark_notification_read(self, notification_id: int, user_id: str = "default") -> bool:
        """Mark a notification as read."""
        cursor = self.db.execute("""
            UPDATE notifications 
            SET read_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND read_at IS NULL
        """, (notification_id, user_id))
        
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def mark_notification_clicked(self, notification_id: int, user_id: str = "default") -> bool:
        """Mark a notification as clicked."""
        cursor = self.db.execute("""
            UPDATE notifications 
            SET clicked_at = CURRENT_TIMESTAMP, read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def dismiss_notification(self, notification_id: int, user_id: str = "default") -> bool:
        """Dismiss a notification."""
        cursor = self.db.execute("""
            UPDATE notifications 
            SET dismissed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def get_notification_summary(self, user_id: str = "default") -> Dict[str, Any]:
        """Get notification summary for dashboard."""
        summary = self.db.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN read_at IS NULL THEN 1 END) as unread,
                COUNT(CASE WHEN priority >= 4 THEN 1 END) as high_priority,
                MAX(created_at) as latest
            FROM notifications 
            WHERE user_id = ?
            AND dismissed_at IS NULL
            AND (expires_at IS NULL OR expires_at > datetime('now'))
        """, (user_id,)).fetchone()
        
        if summary:
            return {
                "total": summary[0],
                "unread": summary[1],
                "high_priority": summary[2],
                "latest": summary[3],
                "has_urgent": summary[2] > 0,
                "needs_attention": summary[1] > 0
            }
        else:
            return {
                "total": 0,
                "unread": 0,
                "high_priority": 0,
                "latest": None,
                "has_urgent": False,
                "needs_attention": False
            }