from app.tasks.analysis_tasks import analyze_subscription_task

result = analyze_subscription_task.delay("28f66da7-dfa0-40c0-b721-317047305f57")
print(f"Task ID: {result.id}")
