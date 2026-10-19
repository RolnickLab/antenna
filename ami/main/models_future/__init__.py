"""
This is a temporary module for adding and updating models and features while we
migrate models.py to a more modular structure. Once the migration is complete,
this module will be renamed and be the location for all models.

Current models will be moved to:

models/
├── __init__.py         # Import everything for backward compatibility
├── base.py             # BaseModel and mixins
├── content.py          # Page, BlogPost
├── enums.py            # TaxonRank and other enums
├── detection.py        # Detection, Classification, Occurrence
├── identifications.py  # Identification
├── images.py           # SourceImage, Event, SourceImageCollection
├── filters.py          # Filters for database queries
├── occurrence.py       # Occurrence rendering
├── projects.py         # Project, Device, Site, Deployment
├── storage.py          # S3StorageSource, SourceImageUpload
└── taxonomy.py         # Taxon, TaxaList, Tag
"""
