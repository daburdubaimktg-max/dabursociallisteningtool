"""Profile/follower adapters — collect a brand's follower count per platform.

These are distinct from the post adapters: they read a *profile's* follower count
(a reach signal) rather than posts/comments. Same contract philosophy
(CLAUDE.md §2): the collection provider (Apify / official API) is abstracted behind
the adapter, fixture-first for offline/test runs, live gated on a token from env.
"""
