from orchestrator.supervisor import create_supervisor


# Create supervisor using factory function
supervisor_agent = create_supervisor()
# Expose the ADK Agent instance as root_agent (required by adk web)
root_agent = supervisor_agent.supervisor_agent