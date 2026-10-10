from django.db import migrations


class Migration(migrations.Migration):
    """Give ``Detection.next_detection`` the unique constraint and foreign key that Django would have created.

    Both are built so that neither blocks reads or writes on the large detection table. The
    unique index is built CONCURRENTLY, which needs a non-atomic migration, and is then attached
    as a constraint, which is a catalogue change. The foreign key is added NOT VALID, so existing
    rows are not checked while a strong lock is held, and validated afterwards, which takes only a
    light lock. See 0093 for why the statement timeout is cleared and restored around the build.

    The constraint names match the ones Django generates, so later AlterField migrations find them.
    If the index build is interrupted it leaves an invalid index of the same name, and if a lock times out the
    index already exists; drop it before retrying.
    """

    atomic = False

    dependencies = [
        ("main", "0100_detection_next_detection"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=(
                'CREATE UNIQUE INDEX CONCURRENTLY "main_detection_next_detection_id_key" '
                'ON "main_detection" ("next_detection_id");'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        # The two ALTER TABLE statements below take brief strong locks. Give up rather than queue behind a long
        # query on the table, which would block every other query until it ends.
        migrations.RunSQL(sql="SET lock_timeout = '10s';", reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "main_detection" ADD CONSTRAINT "main_detection_next_detection_id_key" '
                'UNIQUE USING INDEX "main_detection_next_detection_id_key";'
            ),
            reverse_sql='ALTER TABLE "main_detection" DROP CONSTRAINT "main_detection_next_detection_id_key";',
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "main_detection" ADD CONSTRAINT "main_detection_next_detection_id_f0201e13_fk_main_detection_id" '
                'FOREIGN KEY ("next_detection_id") REFERENCES "main_detection" ("id") '
                "DEFERRABLE INITIALLY DEFERRED NOT VALID;"
            ),
            reverse_sql=(
                'ALTER TABLE "main_detection" '
                'DROP CONSTRAINT "main_detection_next_detection_id_f0201e13_fk_main_detection_id";'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "main_detection" VALIDATE CONSTRAINT '
                '"main_detection_next_detection_id_f0201e13_fk_main_detection_id";'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="RESET lock_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
