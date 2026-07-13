import ami.exports.format_types as format_types


class ExportRegistry:
    _registry = {}

    @classmethod
    def register(cls, format_type):
        """Decorator to register an export format."""

        def decorator(exporter_class):
            cls._registry[format_type] = exporter_class
            return exporter_class

        return decorator

    @classmethod
    def get_exporter(cls, format_type):
        """Retrieve an exporter class based on format type."""
        return cls._registry.get(format_type, None)

    @classmethod
    def get_supported_formats(cls):
        """Return a list of registered formats."""
        return list(cls._registry.keys())


ExportRegistry.register("occurrences_api_json")(format_types.JSONExporter)
ExportRegistry.register("occurrences_simple_csv")(format_types.CSVExporter)
ExportRegistry.register("dwca")(format_types.DwCAExporter)
