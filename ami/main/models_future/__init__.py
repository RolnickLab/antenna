"""
This is a temporary module for adding new models and features while we migrate models.py to a more modular structure.
Once the migration is complete, this module will be removed and the models will be moved to their respective files.

This will happen after the current PRs are merged to minimize conflicts.

Current models will be moved to:

models/
├── __init__.py          # Import everything for backward compatibility
├── base.py             # BaseModel and mixins
├── projects.py         # Project, Device, Site, Deployment
├── storage.py          # S3StorageSource, SourceImageUpload
├── images.py           # SourceImage, Event, SourceImageCollection
├── taxonomy.py         # Taxon, TaxaList, Tag
├── detection.py        # Detection, Classification, Occurrence
├── identification.py   # Identification
├── content.py          # Page, BlogPost
└── enums.py           # TaxonRank and other enums
"""
