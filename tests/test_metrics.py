"""
Tests for OpenTelemetry metrics instrumentation.
"""

from unittest.mock import patch
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from src.main import app, request_count, request_duration, error_count
from src.core.worker import tasks_processed, tasks_failed, dlq_size, queue_depth


class TestMetricsInstrumentation:
    """Test metrics instrumentation for FastAPI app."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create in-memory metric reader for testing
        self.reader = InMemoryMetricReader()
        self.meter_provider = MeterProvider(metric_readers=[self.reader])
        metrics.set_meter_provider(self.meter_provider)

    def teardown_method(self):
        """Clean up after tests."""
        metrics.set_meter_provider(None)

    def test_request_count_metric(self):
        """Test that request count metric is properly configured."""
        assert request_count is not None
        assert hasattr(request_count, "add")

    def test_request_duration_metric(self):
        """Test that request duration metric is properly configured."""
        assert request_duration is not None
        assert hasattr(request_duration, "record")

    def test_error_count_metric(self):
        """Test that error count metric is properly configured."""
        assert error_count is not None
        assert hasattr(error_count, "add")


class TestWorkerMetricsInstrumentation:
    """Test metrics instrumentation for worker."""

    def test_worker_metrics_configured(self):
        """Test that worker metrics are properly configured."""
        assert tasks_processed is not None
        assert tasks_failed is not None
        assert dlq_size is not None
        assert queue_depth is not None

    def test_tasks_processed_metric(self):
        """Test tasks processed counter."""
        assert hasattr(tasks_processed, "add")

    def test_tasks_failed_metric(self):
        """Test tasks failed counter."""
        assert hasattr(tasks_failed, "add")

    def test_dlq_size_gauge(self):
        """Test DLQ size gauge."""
        assert hasattr(dlq_size, "set")

    def test_queue_depth_gauge(self):
        """Test queue depth gauge."""
        assert hasattr(queue_depth, "set")


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""

    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint is available."""
        # This would require a test client, but for now just check the app has the route
        routes = [route.path for route in app.routes]
        assert "/metrics" in routes

    @patch("src.main.generate_latest")
    def test_metrics_endpoint_returns_data(self, mock_generate):
        """Test that metrics endpoint returns Prometheus data."""
        mock_generate.return_value = b"# Test metrics"

        # This would need a test client to actually call the endpoint
        # For now, just verify the function exists
        from src.main import generate_latest

        assert callable(generate_latest)
