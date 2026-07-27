# backend/tools/

Tool implementations exposed to agents (e.g. CRM/billing system lookups,
ticketing system integration, knowledge base search). Agents in
`backend/agents/` consume these rather than implementing raw integrations
inline.

## TODO

- [ ] Define a common tool interface/registration mechanism compatible with both
      LangGraph and CrewAI tool-calling conventions
- [ ] Implement billing system lookup tool
- [ ] Implement ticketing/CRM tool
- [ ] Implement knowledge base search tool
