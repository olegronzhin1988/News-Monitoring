from app.tasks.analysis_tasks import analyze_subscription_task

result = analyze_subscription_task.delay("d183e257-b308-4453-975a-161537cdeb5e")
print(f"Task ID: {result.id}")
