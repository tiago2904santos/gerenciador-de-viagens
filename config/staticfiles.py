from whitenoise.storage import CompressedManifestStaticFilesStorage


class VersionedStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Hash CSS references and JavaScript module imports during collectstatic."""

    support_js_module_import_aggregation = True
