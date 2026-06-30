"""Competitor follower-growth tracking (the "live Excel dashboard" feature).

This module is a SEPARATE dimension from sentiment. Per CLAUDE.md Rule 2
(reach ≠ sentiment), follower counts and growth are a *reach* signal and are
never blended with sentiment label/score. They are tracked, rolled up, and
exported entirely on their own.
"""
