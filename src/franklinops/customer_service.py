from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .audit import AuditLogger
from .opsdb import OpsDB
from .settings import FranklinOpsSettings


class ProactiveCustomerService:
    """
    Built-in customer service system that monitors for issues and provides intelligent assistance.
    
    Features:
    - Proactive issue detection
    - Context-aware help suggestions
    - Error translation to plain English
    - Success coaching and optimization recommendations
    """
    
    def __init__(self, db: OpsDB, audit: AuditLogger, settings: FranklinOpsSettings):
        self.db = db
        self.audit = audit
        self.settings = settings
        self._ensure_service_tables()
    
    def _ensure_service_tables(self):
        """Create customer service tracking tables."""
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS service_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'medium',
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                suggested_solution TEXT,
                context_data TEXT DEFAULT '{}',
                status TEXT DEFAULT 'detected',
                user_notified BOOLEAN DEFAULT FALSE,
                resolved_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS service_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                action_items TEXT DEFAULT '[]',
                expected_benefit TEXT,
                priority_score INTEGER DEFAULT 0,
                context_data TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                user_viewed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS service_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_type TEXT NOT NULL,
                content TEXT NOT NULL,
                user_response TEXT,
                helpful_rating INTEGER NULL,
                feedback_text TEXT DEFAULT '',
                context_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.conn.commit()
    
    def run_proactive_scan(self) -> Dict[str, Any]:
        """Run comprehensive proactive issue detection scan."""
        results = {
            "issues_detected": [],
            "suggestions_generated": [],
            "system_health": {},
            "scan_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Detect configuration issues
        config_issues = self._detect_configuration_issues()
        results["issues_detected"].extend(config_issues)
        
        # Detect workflow issues
        workflow_issues = self._detect_workflow_issues()
        results["issues_detected"].extend(workflow_issues)
        
        # Detect data quality issues
        data_issues = self._detect_data_quality_issues()
        results["issues_detected"].extend(data_issues)
        
        # Generate optimization suggestions
        optimization_suggestions = self._generate_optimization_suggestions()
        results["suggestions_generated"].extend(optimization_suggestions)
        
        # Generate success coaching
        coaching_suggestions = self._generate_success_coaching()
        results["suggestions_generated"].extend(coaching_suggestions)
        
        # Assess overall system health
        results["system_health"] = self._assess_system_health()
        
        # Store results in database
        self._store_scan_results(results)
        
        # Log the scan
        self.audit.append(
            actor="system",
            action="proactive_scan_completed",
            scope="internal",
            details={
                "issues_count": len(results["issues_detected"]),
                "suggestions_count": len(results["suggestions_generated"])
            }
        )
        
        return results
    
    def _detect_configuration_issues(self) -> List[Dict[str, Any]]:
        """Detect configuration-related issues."""
        issues = []
        
        # Check for missing OneDrive paths
        if not self.settings.onedrive_projects_root:
            issues.append({
                "type": "configuration",
                "severity": "high",
                "title": "OneDrive Projects folder not configured",
                "description": "Without connecting your projects folder, I can't help organize your project documents or track deadlines.",
                "solution": "Go to Settings and connect your main projects/jobs folder",
                "quick_fix": {"action": "configure_folder", "folder_type": "projects"},
                "context": {"setting": "onedrive_projects_root"}
            })
        
        if not self.settings.onedrive_bidding_root:
            issues.append({
                "type": "configuration", 
                "severity": "medium",
                "title": "Bidding folder not connected",
                "description": "I can't automatically capture new bidding opportunities without access to your bidding folder.",
                "solution": "Connect your ITB/RFQ/bidding folder to enable automatic opportunity detection",
                "quick_fix": {"action": "configure_folder", "folder_type": "bidding"},
                "context": {"setting": "onedrive_bidding_root"}
            })
        
        # Check for OpenAI configuration
        if not self.settings.openai_api_key:
            issues.append({
                "type": "configuration",
                "severity": "medium", 
                "title": "AI chat not fully enabled",
                "description": "You're missing out on intelligent document analysis and business insights.",
                "solution": "Add your OpenAI API key to enable smart business chat",
                "quick_fix": {"action": "configure_openai_key"},
                "context": {"feature": "ai_chat"}
            })
        
        return issues
    
    def _detect_workflow_issues(self) -> List[Dict[str, Any]]:
        """Detect workflow and process issues."""
        issues = []
        
        # Check for stalled approvals
        stalled_approvals = self.db.execute("""
            SELECT COUNT(*) as count
            FROM approval 
            WHERE status = 'pending' 
            AND created_at < datetime('now', '-3 days')
        """).fetchone()
        
        if stalled_approvals and stalled_approvals[0] > 0:
            issues.append({
                "type": "workflow",
                "severity": "medium",
                "title": f"{stalled_approvals[0]} approvals pending for 3+ days",
                "description": "Delayed approvals can slow down your business operations and delay payments or decisions.",
                "solution": "Review and decide on pending approvals to keep workflows moving",
                "quick_fix": {"action": "show_pending_approvals"},
                "context": {"count": stalled_approvals[0]}
            })
        
        # Check for overdue tasks
        overdue_tasks = self.db.execute("""
            SELECT COUNT(*) as count
            FROM task 
            WHERE status != 'completed' 
            AND due_date < date('now')
        """).fetchone()
        
        if overdue_tasks and overdue_tasks[0] > 0:
            issues.append({
                "type": "workflow",
                "severity": "high",
                "title": f"{overdue_tasks[0]} overdue tasks",
                "description": "Overdue tasks can impact project deadlines and client relationships.",
                "solution": "Review overdue tasks and update their status or reschedule them",
                "quick_fix": {"action": "show_overdue_tasks"},
                "context": {"count": overdue_tasks[0]}
            })
        
        # Check for unpaid invoices aging
        aging_invoices = self.db.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM invoice 
            WHERE status != 'paid' 
            AND created_at < datetime('now', '-30 days')
        """).fetchone()
        
        if aging_invoices and aging_invoices[0] > 0:
            issues.append({
                "type": "workflow",
                "severity": "high",
                "title": f"{aging_invoices[0]} invoices unpaid for 30+ days",
                "description": f"${aging_invoices[1]:,.2f} in aged receivables could impact cash flow.",
                "solution": "Send payment reminders or follow up on overdue accounts",
                "quick_fix": {"action": "run_ar_followup"},
                "context": {"count": aging_invoices[0], "amount": aging_invoices[1]}
            })
        
        return issues
    
    def _detect_data_quality_issues(self) -> List[Dict[str, Any]]:
        """Detect data quality and consistency issues."""
        issues = []
        
        # Check for leads without follow-up actions
        leads_without_followup = self.db.execute("""
            SELECT COUNT(*) as count
            FROM sales_lead sl
            WHERE NOT EXISTS (
                SELECT 1 FROM task t 
                WHERE t.related_entity_type = 'sales_lead' 
                AND t.related_entity_id = sl.id
                AND t.created_at > sl.created_at
            )
            AND sl.created_at < datetime('now', '-7 days')
            AND sl.status = 'active'
        """).fetchone()
        
        if leads_without_followup and leads_without_followup[0] > 0:
            issues.append({
                "type": "data_quality",
                "severity": "medium",
                "title": f"{leads_without_followup[0]} leads have no follow-up actions",
                "description": "Leads without follow-up tasks may be falling through the cracks.",
                "solution": "Create follow-up tasks or qualification calls for inactive leads",
                "quick_fix": {"action": "create_lead_followups"},
                "context": {"count": leads_without_followup[0]}
            })
        
        # Check for missing project information
        incomplete_projects = self.db.execute("""
            SELECT COUNT(*) as count
            FROM project 
            WHERE (customer_id IS NULL OR customer_id = '') 
            AND status = 'active'
        """).fetchone()
        
        if incomplete_projects and incomplete_projects[0] > 0:
            issues.append({
                "type": "data_quality",
                "severity": "low",
                "title": f"{incomplete_projects[0]} projects missing customer information",
                "description": "Projects without customer links make reporting and communication harder.",
                "solution": "Review and complete project customer assignments",
                "quick_fix": {"action": "show_incomplete_projects"},
                "context": {"count": incomplete_projects[0]}
            })
        
        return issues
    
    def _generate_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Generate optimization and improvement suggestions."""
        suggestions = []
        
        # Suggest automation for repetitive tasks
        repetitive_patterns = self.db.execute("""
            SELECT COUNT(*) as manual_count
            FROM audit_event 
            WHERE actor = 'human' 
            AND action LIKE '%manual%'
            AND created_at > datetime('now', '-30 days')
        """).fetchone()
        
        if repetitive_patterns and repetitive_patterns[0] > 10:
            suggestions.append({
                "type": "automation_opportunity",
                "title": "Automate repetitive manual tasks",
                "description": f"I noticed {repetitive_patterns[0]} manual actions in the past month that could be automated.",
                "action_items": [
                    "Review your most common manual tasks",
                    "Set up automation rules for recurring actions",
                    "Enable higher autonomy levels for trusted processes"
                ],
                "expected_benefit": f"Could save 2-5 hours per week by automating common tasks",
                "priority_score": 8,
                "context": {"manual_count": repetitive_patterns[0]}
            })
        
        # Suggest email sequence optimization
        email_performance = self.db.execute("""
            SELECT COUNT(*) as draft_count,
                   COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count
            FROM outbound_message 
            WHERE created_at > datetime('now', '-30 days')
        """).fetchone()
        
        if email_performance and email_performance[0] > 5:
            sent_rate = (email_performance[1] / email_performance[0]) * 100 if email_performance[0] > 0 else 0
            if sent_rate < 70:
                suggestions.append({
                    "type": "process_optimization",
                    "title": "Improve email workflow efficiency",
                    "description": f"Only {sent_rate:.0f}% of drafted emails are being sent. This suggests approval bottlenecks.",
                    "action_items": [
                        "Review email approval thresholds",
                        "Create templates for common email types",
                        "Enable auto-send for low-risk communications"
                    ],
                    "expected_benefit": "Faster customer communication and better response rates",
                    "priority_score": 6,
                    "context": {"draft_count": email_performance[0], "sent_count": email_performance[1]}
                })
        
        return suggestions
    
    def _generate_success_coaching(self) -> List[Dict[str, Any]]:
        """Generate success coaching and celebratory suggestions."""
        suggestions = []
        
        # Calculate time saved through automation
        automation_events = self.db.execute("""
            SELECT COUNT(*) as automated_actions
            FROM audit_event 
            WHERE actor LIKE 'system%' 
            AND action NOT IN ('audit_event_created', 'system_startup', 'system_shutdown')
            AND created_at > datetime('now', '-30 days')
        """).fetchone()
        
        if automation_events and automation_events[0] > 50:
            estimated_time_saved = automation_events[0] * 3  # Assume 3 minutes per automated action
            suggestions.append({
                "type": "success_celebration",
                "title": f"🎉 You've automated {automation_events[0]} tasks this month!",
                "description": f"Estimated time saved: {estimated_time_saved} minutes ({estimated_time_saved/60:.1f} hours)",
                "action_items": [
                    "See which automations are working best for you",
                    "Consider expanding successful automations to similar processes",
                    "Share your success with team members"
                ],
                "expected_benefit": "Continued productivity gains and process improvements",
                "priority_score": 3,
                "context": {"automated_actions": automation_events[0], "time_saved_minutes": estimated_time_saved}
            })
        
        # Suggest advanced features for experienced users
        user_experience_indicators = self.db.execute("""
            SELECT COUNT(DISTINCT action) as unique_actions,
                   COUNT(*) as total_actions
            FROM audit_event 
            WHERE actor = 'human'
            AND created_at > datetime('now', '-30 days')
        """).fetchone()
        
        if user_experience_indicators and user_experience_indicators[1] > 100 and user_experience_indicators[0] > 10:
            suggestions.append({
                "type": "feature_discovery",
                "title": "🚀 Ready for advanced features?",
                "description": f"You've mastered the basics! You've used {user_experience_indicators[0]} different features.",
                "action_items": [
                    "Explore advanced reporting and analytics",
                    "Set up custom automation workflows",
                    "Try the AI-powered business insights features"
                ],
                "expected_benefit": "Unlock even more productivity and business intelligence",
                "priority_score": 4,
                "context": {"unique_actions": user_experience_indicators[0]}
            })
        
        return suggestions
    
    def _assess_system_health(self) -> Dict[str, Any]:
        """Assess overall system health and performance."""
        health = {
            "overall_score": 100,
            "components": {},
            "recommendations": []
        }
        
        # Check database health
        db_size = self.db.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()").fetchone()
        health["components"]["database"] = {
            "status": "healthy",
            "size_mb": (db_size[0] / 1024 / 1024) if db_size else 0
        }
        
        # Check recent activity levels
        recent_activity = self.db.execute("""
            SELECT COUNT(*) as events
            FROM audit_event 
            WHERE created_at > datetime('now', '-7 days')
        """).fetchone()
        
        activity_score = min(100, (recent_activity[0] / 50) * 100) if recent_activity else 0
        health["components"]["activity"] = {
            "status": "active" if activity_score > 50 else "low",
            "score": activity_score,
            "recent_events": recent_activity[0] if recent_activity else 0
        }
        
        # Check automation effectiveness
        automation_ratio = self.db.execute("""
            SELECT 
                COUNT(CASE WHEN actor LIKE 'system%' THEN 1 END) * 100.0 / COUNT(*) as ratio
            FROM audit_event 
            WHERE created_at > datetime('now', '-7 days')
            AND action NOT IN ('audit_event_created', 'system_startup', 'system_shutdown')
        """).fetchone()
        
        auto_score = automation_ratio[0] if automation_ratio and automation_ratio[0] else 0
        health["components"]["automation"] = {
            "status": "optimized" if auto_score > 60 else "growing" if auto_score > 30 else "manual",
            "automation_percentage": auto_score
        }
        
        # Calculate overall health score
        health["overall_score"] = int((activity_score + auto_score) / 2)
        
        # Add recommendations based on health
        if health["overall_score"] < 70:
            health["recommendations"].append("Consider increasing automation levels to improve efficiency")
        if activity_score < 30:
            health["recommendations"].append("System usage is low - check if all integrations are working correctly")
        
        return health
    
    def _store_scan_results(self, results: Dict[str, Any]):
        """Store scan results in the database."""
        # Store detected issues
        for issue in results["issues_detected"]:
            # Check if similar issue already exists
            existing = self.db.execute("""
                SELECT id FROM service_issues 
                WHERE issue_type = ? AND title = ? AND status != 'resolved'
            """, (issue["type"], issue["title"])).fetchone()
            
            if not existing:
                self.db.conn.execute("""
                    INSERT INTO service_issues (issue_type, severity, title, description, suggested_solution, context_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    issue["type"],
                    issue["severity"],
                    issue["title"],
                    issue["description"],
                    issue.get("solution", ""),
                    json.dumps(issue.get("context", {}))
                ))
        
        # Store suggestions
        for suggestion in results["suggestions_generated"]:
            # Check if similar suggestion already exists
            existing = self.db.execute("""
                SELECT id FROM service_suggestions 
                WHERE suggestion_type = ? AND title = ? AND status = 'pending'
            """, (suggestion["type"], suggestion["title"])).fetchone()
            
            if not existing:
                self.db.conn.execute("""
                    INSERT INTO service_suggestions (suggestion_type, title, description, action_items, expected_benefit, priority_score, context_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    suggestion["type"],
                    suggestion["title"],
                    suggestion["description"],
                    json.dumps(suggestion.get("action_items", [])),
                    suggestion.get("expected_benefit", ""),
                    suggestion.get("priority_score", 0),
                    json.dumps(suggestion.get("context", {}))
                ))
        
        self.db.conn.commit()
    
    def get_active_issues(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get currently active issues requiring attention."""
        rows = self.db.execute("""
            SELECT id, issue_type, severity, title, description, suggested_solution, context_data, created_at
            FROM service_issues 
            WHERE status != 'resolved'
            ORDER BY 
                CASE severity 
                    WHEN 'high' THEN 1 
                    WHEN 'medium' THEN 2 
                    WHEN 'low' THEN 3 
                END,
                created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [
            {
                "id": row[0],
                "type": row[1],
                "severity": row[2],
                "title": row[3],
                "description": row[4],
                "solution": row[5],
                "context": json.loads(row[6] or "{}"),
                "created_at": row[7]
            }
            for row in rows
        ]
    
    def get_active_suggestions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get active improvement suggestions."""
        rows = self.db.execute("""
            SELECT id, suggestion_type, title, description, action_items, expected_benefit, priority_score, context_data, created_at
            FROM service_suggestions 
            WHERE status = 'pending'
            ORDER BY priority_score DESC, created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [
            {
                "id": row[0],
                "type": row[1],
                "title": row[2],
                "description": row[3],
                "action_items": json.loads(row[4] or "[]"),
                "expected_benefit": row[5],
                "priority_score": row[6],
                "context": json.loads(row[7] or "{}"),
                "created_at": row[8]
            }
            for row in rows
        ]
    
    def resolve_issue(self, issue_id: int, resolution_note: str = "") -> Dict[str, Any]:
        """Mark an issue as resolved."""
        self.db.conn.execute("""
            UPDATE service_issues 
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (issue_id,))
        self.db.conn.commit()
        
        self.audit.append(
            actor="human",
            action="service_issue_resolved",
            scope="internal",
            details={"issue_id": issue_id, "resolution_note": resolution_note}
        )
        
        return {"success": True, "message": "Issue marked as resolved"}
    
    def dismiss_suggestion(self, suggestion_id: int) -> Dict[str, Any]:
        """Dismiss a suggestion."""
        self.db.conn.execute("""
            UPDATE service_suggestions 
            SET status = 'dismissed'
            WHERE id = ?
        """, (suggestion_id,))
        self.db.conn.commit()
        
        return {"success": True, "message": "Suggestion dismissed"}
    
    def translate_error(self, error_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Translate technical errors into user-friendly explanations with solutions."""
        context = context or {}
        
        error_translations = {
            "ConnectionError": {
                "title": "Connection Problem",
                "explanation": "I'm having trouble connecting to a service or file location.",
                "likely_causes": [
                    "Network connectivity issue",
                    "Service temporarily unavailable", 
                    "File path no longer accessible"
                ],
                "solutions": [
                    "Check your internet connection",
                    "Verify file/folder paths are still valid",
                    "Try again in a few moments"
                ]
            },
            "FileNotFoundError": {
                "title": "File or Folder Not Found",
                "explanation": "I can't find a file or folder that I need to access.",
                "likely_causes": [
                    "File was moved or deleted",
                    "Folder path changed", 
                    "OneDrive sync issues"
                ],
                "solutions": [
                    "Check if the file still exists at the expected location",
                    "Update folder paths in settings if they've changed",
                    "Ensure OneDrive is syncing properly"
                ]
            },
            "PermissionError": {
                "title": "Permission Denied",
                "explanation": "I don't have permission to access a file or folder.",
                "likely_causes": [
                    "File is locked by another program",
                    "Insufficient access permissions",
                    "File is read-only"
                ],
                "solutions": [
                    "Close any programs that might have the file open",
                    "Check file permissions and make sure you have write access",
                    "Try running as administrator if necessary"
                ]
            },
            "HTTPError": {
                "title": "Service Communication Error", 
                "explanation": "There was a problem communicating with an external service.",
                "likely_causes": [
                    "Service is temporarily down",
                    "API key or authentication issue",
                    "Rate limiting or quota exceeded"
                ],
                "solutions": [
                    "Check service status pages",
                    "Verify API keys and credentials are correct",
                    "Wait a few minutes and try again"
                ]
            }
        }
        
        # Find matching error pattern
        error_type = None
        for pattern, translation in error_translations.items():
            if pattern in error_message:
                error_type = pattern
                break
        
        if error_type:
            translation = error_translations[error_type]
            return {
                "success": True,
                "error_type": error_type,
                "user_friendly_title": translation["title"],
                "explanation": translation["explanation"],
                "likely_causes": translation["likely_causes"],
                "solutions": translation["solutions"],
                "original_error": error_message,
                "context": context
            }
        else:
            # Generic translation for unknown errors
            return {
                "success": True,
                "error_type": "generic",
                "user_friendly_title": "Something Went Wrong",
                "explanation": "I encountered an unexpected issue while processing your request.",
                "likely_causes": [
                    "Temporary system glitch",
                    "Unusual data or input",
                    "Service interruption"
                ],
                "solutions": [
                    "Try your request again",
                    "Check if your data/input looks correct",
                    "Contact support if the problem persists"
                ],
                "original_error": error_message,
                "context": context
            }