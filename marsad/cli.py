"""
CLI — واجهة سطر الأوامر
"""
import sys

def main():
    if len(sys.argv) < 2:
        print("Marsad Library v1.0.0")
        print("Usage:")
        print("  marsad workflow              - Run full workflow")
        print("  marsad dashboard [port]      - Run dashboard")
        print("  marsad agents [count]        - Deploy agents")
        print("  marsad emails [count]        - Create emails")
        print("  marsad vault [platform]      - Manage keys")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "workflow":
        from .workflow import Workflow
        wf = Workflow(num_workers=5)
        result = wf.run_full_workflow()
        print(result)
    
    elif cmd == "dashboard":
        from .dashboard.app import Dashboard
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        Dashboard(port=port).run()
    
    elif cmd == "agents":
        from .agents.swarm import AgentSwarm
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        print(AgentSwarm(count=count).deploy())
    
    elif cmd == "emails":
        from .agents.email_agent import EmailAgent
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        agent = EmailAgent()
        emails = agent.create_batch(count)
        print(f"Created {len(emails)} emails")
    
    elif cmd == "vault":
        from .utils.vault import KeyVault
        vault = KeyVault()
        print(f"Platforms: {vault.list_platforms()}")
    
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
