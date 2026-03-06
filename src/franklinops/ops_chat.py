from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from .doc_index import search_doc_index
from .opsdb import OpsDB


def _build_business_prompt(question: str, hits: list[dict[str, Any]], business_context: dict = None) -> str:
    """Build an enhanced business-focused prompt for intelligent assistance."""
    
    ctx_blocks: list[str] = []
    for h in hits:
        c = h["chunk"]
        header = f"📄 {c['source']}:{c['path']}#chunk{c['chunk_index']} (similarity: {h.get('similarity', 'N/A')})"
        ctx_blocks.append(header + "\n" + (c.get("text") or "").strip())

    context = "\n\n---\n\n".join(ctx_blocks) if ctx_blocks else "(no relevant documents found)"
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    return textwrap.dedent(
        f"""
        You are the FranklinOps Business Intelligence Assistant - a friendly, proactive AI that helps users optimize their construction/contracting business operations.

        ## Your Role & Personality:
        - **Proactive & Helpful**: Anticipate needs, suggest optimizations, celebrate successes
        - **Business-Focused**: Understand construction workflows, cash flow, project management
        - **User-Friendly**: Explain technical issues in plain English, offer specific solutions
        - **Trustworthy**: Only use provided data, cite sources, admit when you don't know something

        ## Current Context:
        - **Time**: {current_time}
        - **User Question**: {question}
        - **Business Context**: {json.dumps(business_context or {}, indent=2)}

        ## Available Business Data:
        {context}

        ## Your Response Guidelines:
        1. **Direct Answer**: Address the user's question clearly and concisely
        2. **Business Insights**: Provide relevant analysis, trends, or patterns you notice
        3. **Actionable Suggestions**: Offer specific next steps or optimizations
        4. **Proactive Help**: Suggest related questions or areas they might want to explore
        5. **Source Citations**: Reference specific documents when making claims
        6. **Plain English**: Avoid technical jargon, explain complex concepts simply

        ## Response Format:
        - Start with a direct answer to their question
        - Add insights or analysis if relevant
        - Suggest next steps or optimizations
        - End with a helpful follow-up question or suggestion

        If the available data is insufficient, suggest specific documents or information that would help answer their question better.

        ## Your Response:
        """
    ).strip()


def _call_openai(*, api_key: str, model: str, prompt: str, temperature: float = 0.3) -> tuple[Optional[str], str]:
    """Call OpenAI API for business intelligence responses."""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 2000,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip(), ""
        else:
            return None, "No response content from OpenAI"
            
    except Exception as e:
        return None, str(e)


def _call_ollama_fallback(*, api_url: str, model: str, prompt: str, temperature: float = 0.2, num_ctx: int = 4096) -> tuple[Optional[str], str]:
    """Fallback to Ollama if OpenAI is not available."""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": float(temperature), "num_ctx": int(num_ctx)},
        }
        resp = requests.post(api_url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip(), ""
    except Exception as e:
        return None, str(e)


def _get_business_context(db: OpsDB) -> dict[str, Any]:
    """Gather business context to enhance AI responses."""
    try:
        context = {}
        
        # Get recent activity summary
        recent_tasks = db.conn.execute("SELECT COUNT(*) FROM task WHERE created_at > datetime('now', '-7 days')").fetchone()
        context["recent_tasks_7d"] = recent_tasks[0] if recent_tasks else 0
        
        # Get pending approvals
        pending_approvals = db.conn.execute("SELECT COUNT(*) FROM approval WHERE status = 'pending'").fetchone()
        context["pending_approvals"] = pending_approvals[0] if pending_approvals else 0
        
        # Get invoice summary
        unpaid_invoices = db.conn.execute("SELECT COUNT(*), SUM(amount) FROM invoice WHERE status != 'paid'").fetchone()
        if unpaid_invoices and unpaid_invoices[0]:
            context["unpaid_invoices"] = {"count": unpaid_invoices[0], "total_amount": unpaid_invoices[1] or 0}
        
        # Get recent opportunities
        recent_opps = db.conn.execute("SELECT COUNT(*) FROM sales_opportunity WHERE created_at > datetime('now', '-30 days')").fetchone()
        context["recent_opportunities_30d"] = recent_opps[0] if recent_opps else 0
        
        # Get active projects
        active_projects = db.conn.execute("SELECT COUNT(*) FROM project WHERE status = 'active'").fetchone()
        context["active_projects"] = active_projects[0] if active_projects else 0
        
        return context
        
    except Exception as e:
        return {"error": f"Could not gather business context: {str(e)}"}


def _detect_user_intent(question: str) -> dict[str, Any]:
    """Detect user intent to provide more targeted responses."""
    question_lower = question.lower()
    
    intent_data = {
        "category": "general",
        "urgency": "normal",
        "requires_action": False,
        "suggested_follow_ups": []
    }
    
    # Categorize the question
    if any(keyword in question_lower for keyword in ["invoice", "payment", "bill", "pay", "owe"]):
        intent_data["category"] = "finance"
        intent_data["suggested_follow_ups"] = [
            "Would you like me to check for overdue payments?",
            "Shall I show you the cashflow forecast?",
            "Do you want to set up payment reminders?"
        ]
    elif any(keyword in question_lower for keyword in ["lead", "opportunity", "prospect", "bid", "quote", "customer"]):
        intent_data["category"] = "sales"
        intent_data["suggested_follow_ups"] = [
            "Would you like to review your sales pipeline?",
            "Should I check for overdue follow-ups?",
            "Want me to draft some outreach emails?"
        ]
    elif any(keyword in question_lower for keyword in ["project", "schedule", "deadline", "task"]):
        intent_data["category"] = "projects"
        intent_data["suggested_follow_ups"] = [
            "Need me to check project deadlines?",
            "Should I review task assignments?",
            "Want to see the project status summary?"
        ]
    
    # Detect urgency
    if any(keyword in question_lower for keyword in ["urgent", "asap", "immediately", "overdue", "late", "problem", "issue"]):
        intent_data["urgency"] = "high"
        intent_data["requires_action"] = True
    elif any(keyword in question_lower for keyword in ["soon", "today", "this week", "reminder"]):
        intent_data["urgency"] = "medium"
    
    return intent_data


def ops_chat(
    db: OpsDB,
    *,
    data_dir,
    question: str,
    k: int = 7,
    openai_api_key: str = "",
    openai_model: str = "gpt-4",
    openai_temperature: float = 0.3,
    ollama_api_url: str = "",
    ollama_model: str = "llama3",
    ollama_first: bool = False,
    user_context: dict = None,
) -> dict[str, Any]:
    """Enhanced ops chat. When ollama_first=True, use Ollama (sovereign/local) before OpenAI."""
    
    # Gather business intelligence
    business_context = _get_business_context(db)
    user_intent = _detect_user_intent(question)
    
    # Enhanced document search
    hits = search_doc_index(db, data_dir=data_dir, query=question, k=k)
    
    # Build intelligent business prompt
    enhanced_context = {**business_context, "user_intent": user_intent}
    if user_context:
        enhanced_context.update(user_context)
    
    prompt = _build_business_prompt(question, hits, enhanced_context)

    # Try Ollama first when ollama_first (white-glove sovereign), else OpenAI first
    answer = None
    err = ""
    ai_provider = "none"

    if ollama_first and ollama_api_url:
        answer, err = _call_ollama_fallback(
            api_url=ollama_api_url,
            model=ollama_model,
            prompt=prompt,
            temperature=0.2,
        )
        ai_provider = "ollama" if answer else "ollama_failed"

    if answer is None and openai_api_key:
        answer, err = _call_openai(
            api_key=openai_api_key,
            model=openai_model,
            prompt=prompt,
            temperature=openai_temperature,
        )
        ai_provider = "openai" if answer else "openai_failed"

    if answer is None and ollama_api_url and not ollama_first:
        answer, err = _call_ollama_fallback(
            api_url=ollama_api_url,
            model=ollama_model,
            prompt=prompt,
            temperature=0.2,
        )
        ai_provider = "ollama" if answer else "ollama_failed"

    # Build enhanced citations with business insights
    citations: list[dict[str, Any]] = []
    for h in hits:
        c = h["chunk"]
        citations.append(
            {
                "source": c["source"],
                "path": c["path"],
                "chunk_index": c["chunk_index"],
                "chunk_id": c["chunk_id"],
                "birthmark": c.get("birthmark", ""),
                "similarity": h["similarity"],
                "snippet": (c.get("text") or "")[:400],  # Longer snippets for better context
            }
        )

    # Handle no AI response case
    if answer is None:
        fallback_response = f"""
I found {len(hits)} relevant documents but couldn't process them with AI at the moment. Here's what I found:

{chr(10).join([f"• {c['source']}:{c['path']} - {c['snippet'][:200]}..." for c in citations[:3]])}

**Business Context:**
- Pending approvals: {business_context.get('pending_approvals', 0)}
- Recent tasks (7 days): {business_context.get('recent_tasks_7d', 0)}
- Active projects: {business_context.get('active_projects', 0)}

*To enable AI: set OPENAI_API_KEY or run Ollama locally (ollama serve, ollama pull llama3). Set FRANKLINOPS_OLLAMA_FIRST=true for sovereign mode.*
        """.strip()
        
        return {
            "status": "ai_unavailable",
            "error": err,
            "answer": fallback_response,
            "citations": citations,
            "hits": hits,
            "business_context": business_context,
            "user_intent": user_intent,
            "ai_provider": ai_provider,
            "suggested_actions": user_intent.get("suggested_follow_ups", [])
        }

    return {
        "status": "ok",
        "answer": answer,
        "citations": citations,
        "hits": hits,
        "business_context": business_context,
        "user_intent": user_intent,
        "ai_provider": ai_provider,
        "suggested_actions": user_intent.get("suggested_follow_ups", [])
    }

