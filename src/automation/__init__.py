"""Automation module - Selenium browser management and actions."""

from .actions import AutomationActions
from .browser import BrowserFactory, BrowserManager
from .selectors import SelectorManager

__all__ = ["BrowserFactory", "BrowserManager", "AutomationActions", "SelectorManager"]
