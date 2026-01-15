"""Peewee migrations -- 019_add_user_profile.py.

Create the data_for_personalized_experience table for user profile analysis.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Create the data_for_personalized_experience table."""

    @migrator.create_model
    class DataforPersonalizedExperience(pw.Model):
        id = pw.CharField(max_length=255, primary_key=True)  # 与 user.id 相同
        data = pw.TextField(null=True)  # JSON: {"messages": [...]}
        profile = pw.TextField(null=True)  # JSON: 用户画像
        updated_at = pw.BigIntegerField(null=False)
        created_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "data_for_personalized_experience"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Remove the data_for_personalized_experience table."""

    migrator.remove_model("data_for_personalized_experience")
