from celery import Celery

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend='redis://redis:6379/0',
        broker='redis://redis:6379/0'
    )
    celery.conf.update(app.config)

    # Register tasks
    celery.autodiscover_tasks(['tasks'])  # Ensure 'tasks' is the correct path to your tasks module

    return celery