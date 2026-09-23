from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0095_grant_sync_deployment_to_mldatamanager"),
    ]

    operations = [
        migrations.RunSQL(
            # UPDATE brings an older installed extension up to the version the server ships;
            # CREATE ... IF NOT EXISTS alone leaves it as it was.
            sql="CREATE EXTENSION IF NOT EXISTS vector; ALTER EXTENSION vector UPDATE;",
            # No-op on reverse: the extension may be shared with other features/databases,
            # and dropping it can be restricted in some hosted environments.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
