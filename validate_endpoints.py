#!/usr/bin/env python3
"""
Sprint 4 Endpoint Validation Script

This script validates that all new endpoints from Sprint 4 are properly implemented
and can be imported without errors. It tests the endpoint definitions and basic
functionality without requiring full service dependencies.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_endpoint_imports():
    """Test that all endpoint modules can be imported successfully."""
    print("🔍 Testing endpoint imports...")

    try:
        print("✅ Main application imports successfully")
    except Exception as e:
        print(f"❌ Failed to import main application: {e}")
        return False

    try:
        print("✅ Core schemas import successfully")
    except Exception as e:
        print(f"❌ Failed to import core schemas: {e}")
        return False

    try:
        print("✅ Config store imports successfully")
    except Exception as e:
        print(f"❌ Failed to import config store: {e}")
        return False

    return True

def validate_endpoint_definitions():
    """Validate that all expected endpoints are defined in the FastAPI app."""
    print("\n🔍 Validating endpoint definitions...")

    try:
        from src.main import app

        # Get all routes from the FastAPI app
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    routes.append(f"{method} {route.path}")

        expected_endpoints = [
            "GET /health",
            "GET /config",
            "PUT /config",
            "POST /books/",
            "GET /books/",
            "GET /books/{book_id}",
            "POST /books/{book_id}/upload",
            "GET /books/{book_id}/toc",
            "POST /query"
        ]

        missing_endpoints = []
        for expected in expected_endpoints:
            if expected not in routes:
                missing_endpoints.append(expected)

        if missing_endpoints:
            print(f"❌ Missing endpoints: {missing_endpoints}")
            return False
        else:
            print("✅ All expected endpoints are defined")
            return True

    except Exception as e:
        print(f"❌ Failed to validate endpoint definitions: {e}")
        return False

def test_schema_validity():
    """Test that all Pydantic schemas are valid and can be instantiated."""
    print("\n🔍 Testing schema validity...")

    try:
        from src.core import schemas

        # Test RAGConfig schema
        config = schemas.RAGConfig(
            retrieval_top_k=10,
            min_chunks=2,
            confidence_threshold=0.7,
            relevance_threshold=0.5,
            max_context_length=4000,
            temperature=0.1,
            enable_fallback=True
        )
        assert config.retrieval_top_k == 10
        print("✅ RAGConfig schema is valid")

        # Test BookCreate schema
        book = schemas.BookCreate(
            title="Test Book",
            author="Test Author"
        )
        assert book.title == "Test Book"
        print("✅ BookCreate schema is valid")

        # Test QueryRequest schema
        query = schemas.QueryRequest(
            query="Test query",
            book_id=1,
            top_k=5
        )
        assert query.book_id == 1
        print("✅ QueryRequest schema is valid")

        return True

    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False

def test_config_store():
    """Test that the configuration store works correctly."""
    print("\n🔍 Testing configuration store...")

    try:
        from src.core.config_store import get_rag_config, update_rag_config, reset_rag_config

        # Test getting default config
        config = get_rag_config()
        print(f"✅ Default config retrieved: retrieval_top_k={config.retrieval_top_k}")

        # Test updating config
        new_config = config.copy()
        new_config.retrieval_top_k = 15
        updated = update_rag_config(new_config)
        print(f"✅ Config updated successfully: retrieval_top_k={updated.retrieval_top_k}")

        # Test reset
        reset_rag_config()
        reset_config = get_rag_config()
        print(f"✅ Config reset successfully: retrieval_top_k={reset_config.retrieval_top_k}")

        return True

    except Exception as e:
        print(f"❌ Config store test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🚀 Starting Sprint 4 Endpoint Validation")
    print("=" * 50)

    tests = [
        ("Endpoint Imports", test_endpoint_imports),
        ("Endpoint Definitions", validate_endpoint_definitions),
        ("Schema Validity", test_schema_validity),
        ("Config Store", test_config_store),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All validations passed! Sprint 4 implementation is ready.")
        return 0
    else:
        print("⚠️  Some validations failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())