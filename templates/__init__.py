"""
Template Library
================

Pre-made templates for common application types.

Templates provide starting points with:
- Tech stack configuration
- Pre-defined features and categories
- Design tokens
- Estimated feature count

Available templates:
- saas-starter: Multi-tenant SaaS with auth and billing
- ecommerce: Online store with products, cart, checkout
- admin-dashboard: Admin panel with CRUD operations
- blog-cms: Blog/CMS with posts, categories, comments
- api-service: RESTful API service
"""

from .library import (
    Template,
    TemplateCategory,
    get_template,
    list_templates,
    load_template,
    generate_app_spec,
    generate_features,
)

__all__ = [
    "Template",
    "TemplateCategory",
    "get_template",
    "list_templates",
    "load_template",
    "generate_app_spec",
    "generate_features",
]
