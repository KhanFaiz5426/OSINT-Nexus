"""AI module — LLM integration for planning and analysis.

Components:
- planner: AI-assisted pivot planning (advisory only)
- analyzer: AI-assisted findings analysis (advisory only)
- validator: Hallucination prevention and schema validation

Security: All AI output is untrusted and validated before use.
The LLM never executes tools, URLs, code, or queries directly.
"""
