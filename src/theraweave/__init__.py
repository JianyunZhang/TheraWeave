"""Local, auditable evidence import for target-validation research."""

__version__ = "0.1.0.dev0"

from .project import DiscoveryProject
from .assessment import assess_archive
from .planning import create_plans, review_plan, record_outcome

__all__ = ["DiscoveryProject", "assess_archive", "create_plans", "review_plan", "record_outcome", "__version__"]
