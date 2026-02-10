# Antenna Roadmap — Planning Meeting Board

> 38 themed cards distilled from 754 roadmap items. Each card represents a cluster
> of related features, bugs, or improvements. Cards are sorted by estimated impact
> within each horizon. User stories are ready as detail cards if needed during discussion.

## Quick Stats

| Horizon | Cards | Items | Focus |
|---------|------:|------:|-------|
| now-3mo | 15 | 93 | Trust & partner case studies — what we must do |
| next-6mo | 13 | 304 | Quality of what we have — finish and polish |
| later | 8 | 129 | Long-term vision — stay ready to pivot |
| someday | 2 | 118 | Long-term vision — stay ready to pivot |

---

## NOW (0-3 months) — Must Do

### Card 1: Smarter Species Predictions You Can Trust

**Show predictions at the right level of detail, mask to regional species, and roll up to genus when species-level confidence is low.**

Effort: **XL** | Items: 13 | Areas: ML/AI, UI/UX, Analytics/Viz

*Status: Infrastructure mostly in place (30+ merged PRs). Need to complete class masking UI, calibration research, and rank rollup logic. PR #999 and #788 are in progress.*

**User Stories:**

- As a field ecologist, I want the system to show me genus-level predictions when it can't confidently identify to species, so I don't waste time verifying incorrect species IDs.
- As a project manager, I want predictions restricted to species that actually occur in my region, so I can trust the results for grant reports.
- As a taxonomist, I want to see multiple prediction options with confidence scores, so I can make informed decisions about uncertain identifications.

Key refs: #999, #915, #788, #1029, #944

<details>
<summary>Underlying items (13)</summary>

- Class masking of one of the existing models
- Calibration (What species can we be confident about)
- Training new regional models for improving results for regional species
- Class masking to regional species checklists
- Restrict to species list (Class masking)
- Improve presented prediction results (Filtering, good defaults, post-processing)
- Confidence at higher ranks (Single determination approach & New column to show predictions)
- How to roll up to genus, higher taxon levels
- Roll up taxon ranks, Adapters, Temperature calibration
- Questions threshold logic for family-level identifications
- Display Top 3 labels with confidence score/uncertainty measures
- Display top N predictions
- Confidence & Uncertainty in UI (displaying species-level accuracy)

</details>

---

### Card 2: Cleaner Images, Better Detections

**Automatically filter out blurry, dark, and tiny detections, and track insects across multiple frames to reduce false positives.**

Effort: **XL** | Items: 10 | Areas: ML/AI, UI/UX

*Status: Foundation work completed (32 merged PRs). Tracking infrastructure exists but needs refinement. Quality filters partially implemented. Need to integrate tracking fully and expose controls in UI.*

**User Stories:**

- As a field ecologist, I want the system to automatically hide low-quality detections, so I can focus on verifying clear, identifiable images.
- As a taxonomist, I want to see which detections are actually the same insect appearing in multiple frames, so I don't count the same individual multiple times.
- As a project manager, I want accurate counts without manual cleanup, so I can trust the data for ecological monitoring reports.

Key refs: #1121, #1097, #837, #999, #954

<details>
<summary>Underlying items (10)</summary>

- Integrate Tracking and Feature Vectors to improve prediction results
- Post processing functions (small, blurry, tracking sequential detections) / Reducing noise
- Tracking for counting (biomass estimation)
- Automated Quality Filters (to auto-remove blurry/dark/tiny images)
- Better Detector/Segmenter (segmentation detector/handling overlapping moths)
- Tracking
- Post processing functions – special sauce (small/blurry/tracking)
- Beyond Species ID: biomass estimation/pixel-to-size calibration/tracking
- Post-Processing Functions (Class Masking/small/blurry/darkness filter)
- Good defaults & presets - hiding noise lower quality results

</details>

---

### Card 3: New Processing Pipeline with Partner Testing

**Deploy the next-generation processing pipeline with order-level classification, size estimation, and improved accuracy for partner projects.**

Effort: **XL** | Items: 4 | Areas: ML/AI, Research

*Status: Major infrastructure work completed (16 merged PRs). Order-level classifier code exists but needs integration as replaceable component. Size estimation backend ready, needs UI exposure. Testing plan needed.*

**User Stories:**

- As an ML researcher, I want to integrate the new order-level classifier, so we can improve identification accuracy before attempting species-level ID.
- As a field ecologist, I want size estimates for each detection, so I can analyze biomass and body size distributions.
- As a project manager, I want to test the new pipeline on my project's data, so I can decide when to switch from the old system.

Key refs: #952, #857, #815, #837, #814

<details>
<summary>Underlying items (5)</summary>

- Experiment with multiple models (order-level classifier object detection/clustering)
- Integrate an Order-Level Classifier with the option to replace the current binary classifier
- Order-level classifier (refinement & calibration) and size estimation
- Size estimation (exposing in UI, centimeter calibration, incorporating into models)
- Trait analysis, temporal patterns, biomass, higher rank information, etc

</details>

---

### Card 4: Processing Jobs That Don't Hang

**Fix job failures, stalling, and incorrect status updates so processing runs reliably from start to finish.**

Effort: **L** | Items: 9 | Areas: Infrastructure

*Status: Processing v2 work in progress (2 merged PRs, 4 open issues). Some critical bugs fixed, but stability issues remain. Need queue cleanup, better error handling, and worker improvements.*

**User Stories:**

- As a field ecologist, I want to start a processing job and have it complete without intervention, so I can trust the platform to work overnight.
- As a project manager, I want accurate job progress indicators, so I know when results are ready without constantly refreshing.
- As an ML researcher, I want failed jobs to provide clear error messages, so I can fix model issues quickly.

Key refs: #1112, #1125, #1113, #1123, #1059

<details>
<summary>Underlying items (9)</summary>

- Implement more algorithms and a better worker system
- Run a ML job (Unstable, jobs stop, status not reflected correctly, crops not saved, not all captures processed)
- Fix critical issues with processing service API (milestone #27)
- Processing stability / Processing v2
- Processing and job failing
- Processing stability/stabilization
- Processing Bugs (processing jobs stalling/status updates incorrect)
- Bug: Sessions not automatically created after sync
- Antenna Lite - mobile app for moth traps that automatically registers an annoynmous station

</details>

---

### Card 5: Upload Your Images Without Dev Help

**Provide desktop tools and background sync so field teams can upload large datasets without technical support.**

Effort: **XL** | Items: 7 | Areas: Data-Management, Onboarding

*Status: Some upload infrastructure exists (2 merged PRs). Desktop uploader is tracked (#687, #879, #878) but not started. Manual upload from UI partially works but needs improvement. Offline mobile companion app (#757) is a stretch goal.*

**User Stories:**

- As a field ecologist, I want a desktop app to sync my camera trap images to Antenna, so I don't need to learn command-line tools or contact the dev team.
- As a project manager, I want to upload a folder of images and have them automatically organized by date and station, so I can start processing immediately.
- As a new user, I want to test Antenna with a few images before setting up a full project, so I can evaluate if it meets my needs.

Key refs: #687, #879, #878, #909, #379

<details>
<summary>Underlying items (7)</summary>

- Collaborate on data uploader and image database
- Manual image uploading from UI or background sync of large datasets
- Data uploader (Technician)
- Desktop data uploading tool
- Need a way to upload a bunch of images without full config
- Antenna Go - offline mobile companion app
- Easy desktop application for uploading data from machines to Antenna

</details>

---

### Card 6: Project Quick Start: Upload and Process in Minutes

**Create a streamlined workflow for new users to upload sample images, run processing, and see results without configuring projects or stations.**

Effort: **L** | Items: 4 | Areas: Onboarding

*Status: Concept defined but not implemented. No GitHub tracking yet. Needs design work to determine scope: full wizard vs. simplified draft project creation. Related to upload tools (card 5) and collections rework (card 7).*

**User Stories:**

- As a new user, I want to upload a folder of images and see identified insects within minutes, so I can decide if Antenna works for my data.
- As a project manager, I want to create a draft project for testing without filling out all metadata fields, so I can experiment before committing to a full setup.
- As a field ecologist, I want the platform to be demo-ready for live presentations, so I can show colleagues how it works with real data.

<details>
<summary>Underlying items (4)</summary>

- Ready for seamless live demonstrations
- Implement Project Quick Start feature (MVP for auto-creating draft projects and processing data)
- Quickstart designs/project (Create a quick start project)
- Quick start project / demo

</details>

---

### Card 7: Collections That Make Sense

**Clarify the difference between dynamic filters and fixed datasets, and make collections more natural in the workflow.**

Effort: **L** | Items: 1 | Areas: Data-Management, UI/UX

*Status: Major work completed (6 merged PRs) but terminology and UX still confusing. Open issue #730 tracks remaining work. Need user research to clarify mental models and improve naming/workflow.*

**User Stories:**

- As a taxonomist, I want to create a collection of uncertain identifications to review later, so I can batch my verification work.
- As a project manager, I want to understand which images are in a collection and whether adding more data will change the collection, so I can plan my analysis.
- As a field ecologist, I want collections to feel like natural groupings of data (not technical filters), so I can organize my work intuitively.

Key refs: #730, #895, #636, #1067

<details>
<summary>Underlying items (1)</summary>

- Reworking collections - clarifying & solidifying dynamic filters vs. fixed datasets

</details>

---

### Card 8: Regional Species Lists You Can Edit

**Manage project-specific species lists, import regional checklists, and map classifier output to custom taxonomy.**

Effort: **L** | Items: 15 | Areas: Taxonomy, UI/UX

*Status: Partial implementation exists (PR #580, #356, #850 merged). Core features tracked in #933, #545, #490. Need UI for adding species, mapping algorithm outputs, and managing project vs. global lists. Several bugs need fixes.*

**User Stories:**

- As a project manager, I want to restrict predictions to species known from my region, so I don't get false positives from species that don't occur here.
- As a taxonomist, I want to add new species to the system without developer help, so I can keep pace with field identifications.
- As a field ecologist, I want to flag species of conservation concern so I get alerts when they're detected, so I can prioritize verification.

Key refs: #933, #545, #490, #746, #871

<details>
<summary>Underlying items (15)</summary>

- Implement Global lists vs. Project lists for species
- Mapping species from classifier output to custom lists
- Taxa list of support (makes it possible to filter on species of concern)
- Import the full list of species of concern
- Corrected species list for Panama (mainly for identification of processed data)
- Extend the list of species if needed for labellers?
- Missing Not Identifiable class in OOD environment
- Features for 'Species watch list' / 'species of concern' (economic concern)
- Ability to configure a species list
- Extend the list of taxa when needed (Users have to reach out when taxa are missing)
- Import new species & species images
- Taxonomy Features (adding new species/project-based taxonomy)
- Bug: Can't update name, parents or tags
- Project ID required when changing name/tags of cluster
- Taxonomy - Mapping to algorithms (most important UI feature)

</details>

---

### Card 9: Verification Progress You Can Track

**Show which images have been reviewed, track verification progress, and make it easy to pick up where you left off.**

Effort: **M** | Items: 6 | Areas: UI/UX

*Status: Basic filtering exists (#841 merged) but UX needs improvement. Issues #1032, #1093, #560 track gaps. Need clearer visual indicators, better filter UI, and automatic hiding of verified items. Some features completed but need refinement.*

**User Stories:**

- As a taxonomist, I want to see which occurrences I've already verified, so I don't waste time reviewing the same insects twice.
- As a project manager, I want a progress indicator showing what percentage of detections have been reviewed, so I can plan when analysis is ready.
- As a field ecologist, I want to filter to show only unverified images, so I can focus my effort efficiently.

Key refs: #1032, #1093, #560

<details>
<summary>Underlying items (6)</summary>

- Filtering by what has been vetted
- Tracking Progress: Knowing what's been processed/verified
- Hide occurrences if missing detections
- The modal window for taxon should keep on the occurrences / other context instead of sending back to taxa list
- Make detection box directly clickable
- Make all detections visible

</details>

---

### Card 10: Password Reset and Signup Fixes

**Fix broken password reset flow and enable self-service signup so users can access the platform without admin intervention.**

Effort: **M** | Items: 5 | Areas: Permissions/Auth

*Status: Password reset partially fixed (PR #526 merged) but still unstable (#671 open). Signup currently disabled and requires admin support. No clear plan for re-enabling. Shared credentials issue also noted. Need to test and stabilize before public launch.*

**User Stories:**

- As a new user, I want to create an account without emailing the admin, so I can start testing the platform immediately.
- As a field ecologist, I want password reset to work reliably when I'm locked out, so I don't lose access during critical field seasons.
- As a project manager, I want to invite team members who can create their own accounts, so I don't have to coordinate with the dev team.

Key refs: #671, #526

<details>
<summary>Underlying items (5)</summary>

- Reset password when not logged in (Backend configuration is incomplete maybe disable)
- Bug: Sign up as new user requires admin support (currently disabled)
- Bug: Reset password when not logged in is unstable
- Issue of shared credentials
- Sign up as new user on the platform

</details>

---

### Card 11: Team Member Management

**Project managers can invite users, assign roles, and configure permissions without developer help.**

Effort: **L** | Items: 6 | Areas: Permissions/Auth, UI/UX

*Status: Backend permissions exist (PR #851 merged). Role management UI tracked in #1030 and #1006 but not completed. Some closed attempts (#727, #402). Need to complete UI and test end-to-end workflow. Consider how this relates to signup (card 10).*

**User Stories:**

- As a project manager, I want to invite collaborators and assign them roles (viewer, identifier, manager), so I can delegate work without risking data integrity.
- As a taxonomist, I want permissions to edit species lists but not project settings, so I can do my job without accidentally breaking things.
- As a field ecologist, I want to see who verified each occurrence, so I can follow up with questions about uncertain identifications.

Key refs: #1030, #1035, #851

<details>
<summary>Underlying items (6)</summary>

- Add Taxa model permissions to Identifier role
- Configure members for a project (Anna and Mohamed is currently working on this)
- Create user interface for project managers to add new users and assign roles
- Role Management UI (for Project Managers to invite members and assign roles)
- Role management (what about adding new users?)
- User Account Management (re-enabling self-service sign-up)

</details>

---

### Card 12: Data Exports for Partners and Publications

**Export occurrence data, images, and statistics in formats needed for grants, publications, and external analysis tools.**

Effort: **M** | Items: 2 | Areas: Export/Interop

*Status: Feature exists in code but may not be self-service or meet all partner needs. No GitHub tracking found. Need to clarify requirements with users (Yves mentioned for grant writing). Consider formats: CSV, Darwin Core, image archives, etc.*

**User Stories:**

- As a project manager, I want to export occurrence data with metadata for grant reports, so I can demonstrate project impact to funders.
- As an ML researcher, I want to download labeled images for model training, so I can improve classifier accuracy.
- As a field ecologist, I want to export species lists and abundance data for analysis in R, so I can integrate Antenna data with my existing workflows.

<details>
<summary>Underlying items (2)</summary>

- Data Exports (Yves needed for writing grant)
- Exports & Downloads (Self-service feature remaining)

</details>

---

### Card 13: Fix Data Import and Timestamp Issues

**Handle diverse filename formats, fix session auto-creation bugs, and improve data integrity for imported images.**

Effort: **M** | Items: 3 | Areas: Data-Management, Infrastructure

*Status: Several timestamp fixes merged (#781, #778, #644) but format issues remain (#1107, #273, #398 open). Session auto-creation bug tracked in #793 and partially fixed. Sample captures have filename format requirements that need relaxing. Need systematic testing of common formats.*

**User Stories:**

- As a field ecologist, I want images with timestamps in any common format to import correctly, so I don't have to rename thousands of files.
- As a project manager, I want sessions to be automatically created when I upload images, so I can immediately start reviewing data organized by night.
- As a taxonomist, I want confidence that all uploaded images are processed and visible, so I don't miss rare species due to import bugs.

Key refs: #781, #778, #1107, #273, #793

<details>
<summary>Underlying items (3)</summary>

- Fix issues with timestamps not being recognized in the current format
- Sample captures only valid when image file name is in YYYYMMDDHHMMSS format
- Data Integrity Issues (sessions not auto-created/null in data sync view)

</details>

---

### Card 14: UI Polish: Consistent Saving and Better Flows

**Fix inconsistent save behavior, improve page navigation, and make UI interactions more predictable.**

Effort: **M** | Items: 3 | Areas: UI/UX

*Status: Multiple UX gaps identified but not tracked in GitHub. Consistent saving behavior is a recurring complaint. Modal navigation issues noted. Need design review to establish patterns and fix systematically rather than piecemeal.*

**User Stories:**

- As a taxonomist, I want save buttons to behave consistently across all pages, so I don't lose work due to confusion about whether changes were saved.
- As a field ecologist, I want modal windows to stay in context instead of redirecting me to unrelated pages, so I can maintain my workflow.
- As a project manager, I want the UI to feel polished and predictable, so I can confidently train new team members.

<details>
<summary>Underlying items (3)</summary>

- Consistent saving behavior
- The modal window for taxon should keep on the occurrences / other context instead of sending back to taxa list
- Tracking Progress: Knowing what's been processed/verified

</details>

---

### Card 15: Performance: Faster Taxa Pages and Database Access

**Optimize slow queries, improve page load times, and enable online/offline functionality for field use.**

Effort: **L** | Items: 5 | Areas: Infrastructure, DevEx

*Status: Major performance fixes merged (#249, #777, #828, #853) but taxa page still slow (#1045 open). Database snapshots tracked in #514. Offline functionality (#538) is ambitious for this horizon but infrastructure work helps. Image resizing (#419) also impacts performance.*

**User Stories:**

- As a taxonomist, I want the species list page to load in seconds not minutes, so I can quickly navigate to the taxa I need to verify.
- As an ML researcher, I want database snapshots for testing, so I can reproduce bugs and test improvements locally.
- As a field ecologist, I want basic offline functionality so I can review data in the field without internet access.

Key refs: #249, #777, #828, #1045, #514

<details>
<summary>Underlying items (5)</summary>

- Online/Offline functionality
- Resizing images for the app (use prisma urls in API response)
- Taxa page speed (fix in progress) and Species views (too slow)
- Enhance user experience for large image uploads through integration with cloud services
- Better db snapshots for automated and manual testing

</details>

---

## NEXT (3-6 months) — Should Do

### Card 16: ML Pipeline Management and Configuration

**Choose and configure ML models to process your camera trap images with the right algorithms.**

Effort: **XL** | Items: 56 | Areas: Analytics/Viz, DevEx, Documentation, Taxonomy, Research, Infrastructure, UI/UX, ML/AI

*Status: 35 partial, 3 tracked, 7 new*

**User Stories:**

- As a project manager, I want to see which ML models are available and what species they can identify, so I can choose the right one for my region
- As an ML researcher, I want to deploy my custom models through a simple API, so I can test new algorithms on real-world data
- As a field ecologist, I want the platform to remember my preferred model for each project, so I don't have to reconfigure it each time

Key refs: #1011, #1076, #1089, #1092, #1093

<details>
<summary>Underlying items (56)</summary>

- Select project classifier etc. (More one-click options for processing the data)
- Ability to flag species outside classifier taxonomy
- Pipeline config from UI?
- Stats metrics & charts for validation quality control and improving models
- Display species lists known by each model
- Expose more details about each pipeline (ID URL version) in customizable pipelines feature
- Add active/inactive field for pipelines show inactive pipelines below and make them unselectable for new data processing
- Make Access Key for pipelines visible (not a password field)
- Implement Flatbug and AMBER models
- Model registry links to experiment details in WandB
- Default pipelines by project/location
- Additional ML backends
- Feature for masking predictions to a species list (as an alternative to a regional model)
- New model for Panama (current models include P. interpunctella and v2 has a short species list)
- Panama plus model? Needs review uses a different species list.
- Deploy some of Kat's models to a server
- Retrain the model for Totumas data?
- New model on Newfoundland species list (Current Quebec model is overestimating total number of species)
- Option to use model consensus instead of top confidence score (consensus between global & regional model or versions of panama models)
- Configure processing services for a project
- Detector with segmentation (for biomass estimation)
- Segmentation detector (e.g., HQ Sam, GroundingSAM, Depth Anything, Flatbug, OWLv2)
- Discuss detector approaches
- How to score confidence (hardness to identify visually, how many similar species, the models accuracy on this species, the number and quality of training samples (or type of images) for this species). Do we know about it at all? How likely is the species to occur at the place and time it was observed?
- How to incorporate geopriors exactly? Part of model, or post-filtering.
- Object detector only works... (implied limitation)
- Out-of-Distribution (OOD) feature (Mockups, protocol for detecting new species, feature vectors, Yuyan's model)
- Reprocessing detections with a new classifier
- Order level classifier (Aditya's work)
- Species of concern model (invasive & pest species)
- Review current models (trained when, checklists)
- Processing pipeline for analyzing individual images
- Test sets for standard evaluation of models
- Use the zero-shot model
- Missing Singapore classifier option
- Partner-Specific Pipelines (e.g. dedicated forest pest pipeline)
- Model Management (model orchestration & revision/deploying new models)
- Metrics for scaling - how much human validation is necessary to trust the model
- Registration of pipelines (Self-service feature remaining)
- Model Registry & Available Pipelines (Registry for models & ML backends)
- Work on integration structure of models and training data
- Inference page for easily testing all models (without project setup, etc)
- Dedicated interface for testing models (e.g. using Streamlit or Solara)
- Taxonomy database with our own metadata (Cryptic status, Size or size category, Model performance/training info)
- Configure processing services/pipelines
- Improving the results
- Work on new uncertainty measurements
- ML processing done via web API support for any language or framework
- Embarrassing things (IDing smudges with high confidence single subject images)
- More informative confidence scores (calibrated scores)
- Estimating confidence how to present low-confidence results to users
- Integrate Out-of-Distribution (OOD) features for data curation (tagging, moving occurrences between clusters)
- Handle overlapping moths
- Transparency: This region is not supported
- How to choose ID from a track / turboid of multiple images
- Implement enhanced post-processing techniques (moths & insects specific)

</details>

---

### Card 17: Collections and Data Organization

**Group images into logical collections and track what's been uploaded, processed, and verified.**

Effort: **XL** | Items: 47 | Areas: UI/UX, Infrastructure, Permissions/Auth, Documentation, Onboarding, Export/Interop, Taxonomy, Data-Management

*Status: 12 partial, 3 tracked, 19 new*

**User Stories:**

- As a field ecologist, I want to organize images into seasonal collections, so I can process and compare data by year
- As a project manager, I want to see which images have been processed and which are still waiting, so I can track project status
- As a new user, I want drag-and-drop upload for manual testing, so I can try the platform with a few images before committing

Key refs: #1037, #1047, #1078, #1093, #1106

<details>
<summary>Underlying items (47)</summary>

- Remove "null" that keeps returning to data sync view
- More quick buttons for processing & collections
- Processing convenience (buttons for process this night, process this collection)
- Make occurrences in collections clickable
- Implement drag and drop feature for manual uploads
- How can we make collections more natural in the workflow
- Onboarding Flow (Centrally Managed Antenna & UI flow)
- Scratch/draft project based on images (upload a folder)
- Develop a Data connector app (MVP feature)
- Define if collections are reusable (design question)
- Implement default or automatic collections
- Clarify the term Collections with alternatives like Sample set Lists Datasets
- Continue to maintain filename format check for manual uploads
- Importing already-processed data into Antenna
- Data management issues (rotated images/missing metadata/bad data)
- Importing - Captures (import a list of public HTTP urls)
- Will we always require collections for processing?
- Occurrence collections
- Predefined collections / Dynamic presets
- Upload data to the storage (desktop app) (Currently happens outside Antenna using tools like Cyberduck)
- Fix initial difficulty with configuring Amazon S3 settings
- Support for web-connected devices (continuous upload & processing)
- Taxonomy management (External sources/managing taxa/lists/synonyms)
- Importing - Taxa lists
- Provide easier method to export and organize cropped images hierarchically by taxonomy
- Project manager (role/tooling)
- Clarify/flesh out what processing means when a collection is launched
- Configure a data source for a station
- Setup a collection of captures
- Clarify that collections are fixed queries until recalculation
- Emphasize importance of proving data origin
- Confusion about implications of renaming folders and files within the object store
- Research & document plan for easier data import from cameras/SD cards
- Configure a storage/data source
- Registration & map of camera deployments (metadata)
- Label each SD card with tape them and label them
- Make sure the SD card is identify to see from which camera it came from
- Sync the SD cards every day to hardware 1 & 2
- Sync to the cloud (Anna)
- Fresh SD cards
- Project ID required when changing name/tags of cluster
- Non-timeseries data - Microscopy & field photos
- Continue to maintain comprehensive capabilities for managing and analyzing large datasets
- Add context pictures of devices in the field
- Possibility of shorter deployments
- Tags for occurrences
- Missing images

</details>

---

### Card 18: Taxonomy Features and Species Management

**Manage pest species lists, add size fields, handle cryptic species, and roll up counts by taxonomic rank.**

Effort: **XL** | Items: 29 | Areas: ML/AI, Taxonomy, UI/UX, Data-Management

*Status: 7 partial, 7 tracked, 13 new*

**User Stories:**

- As a field ecologist, I want to mark certain species as pests and get alerts when they're detected, so I can respond quickly
- As a taxonomist, I want to roll up species-level counts to genus or family, so I can analyze data at higher taxonomic levels
- As an ML researcher, I want to flag cryptic species complexes, so users know when visual ID alone isn't sufficient

Key refs: #384, #412, #421, #469, #517

<details>
<summary>Underlying items (29)</summary>

- Support experts in finding the correct species within the tool
- Notification system (Species of interest)
- Alerts & notifications (region & species)
- "Species of Interest" feature
- Species page functionality/improvement
- Add alerts for species on user watch lists
- Support for unknown species (clustering)
- Geofencing using species list for improving results
- Downgrading predictions to higher taxonomic ranks until confidence is satisfactory.
- Species dataset made for image classification
- OOD Feature Refinement (for "unexpected species" flagging)
- Genus level prediction (? - evaluate the accuracy at genus level)
- Transparency: Knowing what we don't know - which species good and bad at
- Determine our certainty / uncertainty at predicting that species
- Use Google spreadsheets for collaborative updates to species lists and training data
- Interface for managing species
- Add is_cryptic field (to what rank)
- Features for 'Species of conservation concern' / 'Species of risk'
- Features for 'Pest species'
- Features for 'Non-native' species
- Provisional lists of species (regional lists)
- Rank roll-ups
- Taxon rank rollup (genus, family level predictions) - never show a low confidence result
- Remove species that should not be classified (get checklists from experts)
- Allow viewing IDs by genus/family/etc.
- Rank rollups
- Taxonomy (Hierarchical categories/Many taxonomic ranks)
- Add a field to the taxa DB for unidentifiable by image alone with relation to similar taxa
- Add Not Identifiable and Lepidoptera entry IDs

</details>

---

### Card 19: Platform Documentation and User Guides

**Find clear instructions for self-hosting, connecting ML services, and using all platform features.**

Effort: **XL** | Items: 36 | Areas: DevEx, Documentation, Data-Management

*Status: 1 partial, 24 new*

**User Stories:**

- As a new user, I want step-by-step guides for uploading images and running my first ML job, so I can get started without asking for help
- As an ML researcher, I want documentation on the processing service API contract, so I can integrate my models correctly
- As a field ecologist, I want tooltips and contextual help throughout the interface, so I understand what each feature does

Key refs: #258, PR#1002, PR#1065, PR#1068, PR#158

<details>
<summary>Underlying items (36)</summary>

- Help renaming files from new camera
- New sprint schedule: 3 weeks development, 1 week for documentation and planning
- Provide more guidance/documentation on collections (definition purpose how to use strategy)
- Prioritize documentation for the verification process
- Documentation for reviewing
- Complete documentation & improving self-service
- Exporting data & updating the offline guide
- Configure pipelines for a project (Needs documentation)
- Link to documentation (and write documentation!) / Documentation Sprint
- Use LLM to help with the table of contents for documentation
- Documentation of how to re-train a model with data from Antenna
- Needs documentation for configuring processing services, pipelines, storage, and data source
- Requirements doc - Mapping the pipeline - Documentation for internal use - Showing where the gaps are in the steps
- Documentation - first for internal then for public
- Training support team documentation/videos (Public/Private Wiki, User Manual)
- Provide instructions for uploading large batches of images using Cyberduck
- Circle back to OpenAPI docs to allow researchers to query occurrences in R
- More inline help for users
- New home for Antenna docs!
- At least one documentation ticket
- Make an instructions file about the frontend overall
- Documentation - for users (user guide) and developers
- Configure processing services for a project (Needs documentation)
- Configure a data source for a station (Needs documentation)
- Documentation & doc links within app
- Create logic diagrams for new & existing features
- Add megadector-> butterflies example.
- Antenna workflow/requirements
- One good case study.
- Clarify confirmation of moth presence over multiple days
- Clarify confusion about data flow and image processing integration
- Assumption of manual entry for first & last date
- Clarify device and deployment hierarchies with diagrams or text explanations
- Create Wiki manual with specific process notes
- Suggest avoiding spaces in folder names for better compatibility
- RUNNING ANTENNA LOCALLY

</details>

---

### Card 20: Charts, Stats, and Phenology Analysis

**Visualize species flight times, abundance patterns, and data quality metrics across your monitoring sites.**

Effort: **XL** | Items: 20 | Areas: Analytics/Viz, ML/AI, Data-Management

*Status: 2 partial, 15 new*

**User Stories:**

- As a field ecologist, I want to see flight time charts for each species, so I can identify seasonal patterns and trends
- As a taxonomist, I want to see confidence statistics while verifying, so I know which taxa need more expert review
- As a project manager, I want to spot anomalies like missing capture nights or resolution changes, so I can troubleshoot hardware issues

Key refs: #273, #399, #410, #774, PR#1029

<details>
<summary>Underlying items (20)</summary>

- Filter charts by a given year - to view whole season (Seasonal flight over the year)
- X-axis for Seasonal flight charts should use dates
- Address caveat: dynamic charts only show what is processed (but make it look like everything is processed)
- Default charts feature
- Some basic analysis built in to compare these species of interest
- Michael to assist with analysis and charts for new paper
- Show evalutation stats while validating
- Configure overview stats for a project (Needs more information and user discussions)
- See charts for troubleshooting (not analysis) (Needs more information and user discussions)
- Showing some evaluation & statistics within the UI / Summary metrics as you go
- Default to order level & wider metrics
- Visualizations / aggregation (flight charts) BUT need to only show results we are confident for
- Continue to maintain and enhance automatic visualizations and data organization features
- Features for data analysis: Flight charts and maps with data
- Summary metrics as you go (for troubleshooting/improving results)
- Research focus on uncertainty metrics and UI/UX features for predictions
- Develop dynamic session partitioning for better data visualization and analysis
- Currently 'Captures per hour' is total cumulative captures from all nights on a given night
- The ability to see where the problems are happening
- Time series images (specific automated captured)

</details>

---

### Card 21: UI Polish and Navigation Improvements

**Cleaner filters, better gallery views, smarter defaults, and smoother workflows throughout the interface.**

Effort: **XL** | Items: 20 | Areas: Permissions/Auth, ML/AI, UI/UX, Data-Management

*Status: 3 partial, 3 tracked, 10 new*

**User Stories:**

- As a field ecologist, I want filters to stay applied when navigating between pages, so I don't lose my place
- As a taxonomist, I want to see the best detection image in occurrence lists, so I can quickly assess image quality
- As a project manager, I want clearer visual indicators of what's processed and verified, so I can track team progress at a glance

Key refs: #1063, #1093, #206, #224, #237

<details>
<summary>Underlying items (20)</summary>

- Display user's seen occurrences in My Antenna
- Filtering: Find a clear way to do it yet
- User interface (General Topic)
- Display Images for deployments
- Developing new UI components (new scrolling timeline)
- Default filter: lepidoptera
- New filters: Which nights were captured by all stations? Filter out extra nights
- Improve explanations and add more contextual information about displayed data
- Add advanced filtering options
- Default filters & project settings
- Make session detail more clear
- See results that are accurate enough (Improve filtering, post-processing, pre-configurations)
- Improving/Reducing noise in results displayed by default
- Still some sessions with unprocessed images
- Provide a more dynamic way to handle sessions and timestamps
- Open to the public for read-only review (Next 6 months)
- Complete migration of UI components from raw Radix primitives to shadcn/ui
- Complete migration from style modules to Tailwind CSS
- Streamline form handling across app
- Separating workflows per user category

</details>

---

### Card 22: Export Formats and Data Sharing APIs

**Export occurrence data to Darwin Core, download images for ML retraining, and query data via REST API.**

Effort: **XL** | Items: 16 | Areas: Infrastructure, Export/Interop

*Status: 2 partial, 2 tracked, 10 new*

**User Stories:**

- As a field ecologist, I want to export verified occurrences to Darwin Core format, so I can publish data to GBIF
- As an ML researcher, I want to download all detections with their bounding boxes and labels, so I can retrain models with verified data
- As a project manager, I want to query occurrence data via API, so I can integrate results into our lab's analysis pipelines

Key refs: #258, #298, #304, #307, #413

<details>
<summary>Underlying items (16)</summary>

- Enable remote data transfer from isolated northern deployments
- Exporting data (General Topic)
- Exports
- Data Exports: Darwin Core for biologists and bioinformatics people
- Data Exports: COCO/YOLO formats for re-training purposes (ML researchers)
- Darwincore export and Export format for ML retraining
- Implement a Taxa List Filter and support Darwin Core Export Format
- Implement export options
- Replicate desktop/offline version export options
- Add missing fields related to images when exporting to CSV
- Download X amount of photos for a species list with high confidence
- New export format geared toward ML with previous predictions/corrected IDs
- Exports to DARWIN core
- Export Formats (Darwin Core/COCO/YOLO formats)
- API (General Topic)
- Data access for fine-tuning - ML research

</details>

---

### Card 23: Review Workflow and Progress Tracking

**Track verification progress, get notified about important events, and streamline species review workflows.**

Effort: **L** | Items: 13 | Areas: UI/UX, Data-Management, ML/AI, Analytics/Viz, Taxonomy

*Status: 13 items combined*

**User Stories:**

- As a taxonomist, I want to bulk-label multiple similar occurrences at once, so I can process hundreds of images efficiently
- As a field ecologist, I want to see which nights have been processed and verified, so I can prioritize my workflow
- As a project manager, I want email alerts when large processing jobs finish, so I know when to review results

Key refs: PR#1058, #904, #832, #216, #833

<details>
<summary>Underlying items (13)</summary>

- Labeling at scale - entomologists
- Add column for best_identification to the occurrences view (optional, next to Taxon Determination column)
- Filter/search by previous identifications
- Labeling interface - Bulk labeling from the grid view
- Implement method for bulk updating of incorrect timestamps
- Add fields for barcode bin numbers to assist with species identification
- Showing what has been processed
- Showing some evaluation & statistics within the UI
- Fix inconsistent Processed counts in job logs
- Occurrence tracking
- Notifications
- Alerts feature
- Add general notifications

</details>

---

### Card 24: Performance, Optimization, and Database Scaling

**Speed up page loads, optimize queries, and handle larger datasets without performance degradation.**

Effort: **XL** | Items: 28 | Areas: Infrastructure, Taxonomy

*Status: 9 partial, 1 tracked*

**User Stories:**

- As a project manager, I want projects with 100k+ images to load quickly, so I don't have to wait minutes for each page
- As a field ecologist, I want occurrence filters to respond instantly, so I can explore my data interactively
- As an ML researcher, I want to process thousands of images without slowing down the platform for other users

Key refs: #1097, #217, #236, #239, #258

<details>
<summary>Underlying items (28)</summary>

- Speed up deployments list?
- Bug: Increase capacity of the database in the OOD environment
- DB Table partitions (Partitioning/Database Scaling/Optimization)
- Optimization features & "hardening" (including Image resizing)
- Speed/Performance (Top priority, scaling up processing)
- Stable production environment with automated backups & good performance
- Setup vector database
- Note on slow overall internet affecting performance
- Add cryptic species status to the taxonomy database: Euceron species should always be determined to genus level
- Add size fields to the taxonomy database (fallback to parent size category). Avg.
- Background job system logging per job
- Run an XL ML job (VISS project)
- Time for refactoring (switching to Next.js)
- Migrate to React 19
- Migrate to Next.js (to simplify routing and code splitting)
- Focus on portability, quick install, cloud & local
- Script to fix date offsets
- Scaling up infrastructure (robustness)
- Fix slower image loading
- Fix very slow image loading
- Increase image resolution threshold to accommodate high-resolution images
- Stability issues on the platform
- DB partitioning exploration and implementation
- IMAGE THUMBNAILING - Faster scrubbing (mp4s)
- Switch from form data to application/json
- Browser-based regression / integration tests (Cypress/Playwright)
- More full stack dev, easier integration from ML experiments to platform
- Streamline form handling across app

</details>

---

### Card 25: User Signup and Project Creation Flow

**Sign up for an account and create your first project with guided setup and quick-start templates.**

Effort: **XL** | Items: 16 | Areas: Onboarding, Documentation, UI/UX, Infrastructure

*Status: 1 partial, 9 new*

**User Stories:**

- As a new user, I want to sign up without waiting for admin approval, so I can start evaluating the platform immediately
- As a field ecologist, I want a quick-start wizard that creates a draft project from uploaded images, so I can see results in minutes
- As a project manager, I want a landing page with a live demo, so I can show stakeholders what the platform does before committing

Key refs: #1088, #344, #648, #714, PR#152

<details>
<summary>Underlying items (16)</summary>

- Public splash page/landing page with a demo feature and interest form
- Design stable & streamlined workflow: Get from Cameras to moths with few steps
- Sign up on the platform waitlist
- Sign up as new user on the platform (Currently disabled manually add new users)
- Sign up as new user (currently requires admin support)
- Account Sign-ups (Self-service feature remaining, currently requires admin support)
- New project Wizard
- Self-service features (using feature-flags/complexity as opt-in)
- Multiple environments and auto deployment (Dev, Staging, Branch deploys, Demo, Production)
- Demonstration for self-installation
- All-in-one test page
- Create a project from scratch (Currently disabled for most users soon enabled for all)
- Create a project from scratch (Partially implemented/disabled for most)
- Feature Rollout: Create a project from scratch is partially implemented
- Create a project from scratch
- Create a project from scratch (Partially implemented)

</details>

---

### Card 26: Detection Editing and Manual Annotation

**Draw boxes around missed insects and correct automated detections to improve your dataset quality.**

Effort: **XL** | Items: 9 | Areas: ML/AI, UI/UX, Data-Management

*Status: 4 partial, 2 tracked, 3 new*

**User Stories:**

- As a taxonomist, I want to draw a box around insects the detector missed, so I can create complete species records
- As a field ecologist, I want to adjust detection boxes that are incorrectly positioned, so the cropped images show the whole insect
- As an ML researcher, I want to export manually corrected detections, so I can retrain my model with higher quality data

Key refs: #1047, #1093, #304, #400, #413

<details>
<summary>Underlying items (9)</summary>

- Show best detection image in taxa view & occurrence view
- Expose specific data source subdirectory in Deployment edit
- Fix issue with re-choosing Site & Device when editing a Deployment
- Allow drawing box to add missed moth in session review
- Labeling Interface Improvements (bulk labeling/editing bounding boxes)
- Continuous OOD detection (combined with clustering; how to remove the OOD species that have been verified)
- Hide occurrences if missing detections
- Suggests classification of derived data: Detections -> Occurrences -> Species
- Continue to maintain the ability to add and edit information about devices and deployments

</details>

---

### Card 27: Project Settings and Data Quality Tools

**Configure project defaults, detect data anomalies, and maintain high-quality datasets.**

Effort: **M** | Items: 9 | Areas: UI/UX, ML/AI, Analytics/Viz, Infrastructure

*Status: 9 items combined*

**User Stories:**

- As a project manager, I want to configure default filters and score thresholds per project, so team members see consistent results
- As a field ecologist, I want to be alerted when a deployment stops capturing images, so I can fix hardware issues quickly
- As an ML researcher, I want to enable experimental features for my project, so I can test new capabilities without affecting others

Key refs: #344, #1110, PR#1002, PR#699, PR#1065

<details>
<summary>Underlying items (9)</summary>

- Consider mitigating psychological/positional bias in accepting proposed labels
- How can we make the data output more satisfactory?
- How can we highlight anomalies in the capture images (out of schedule, short schedule, strange dates, mixed resolution images)
- Post-processing based on image quality (what are we unconfident about)
- Improving image quality of cameras
- How to trigger post process steps from UI?
- Project Settings & feature flags
- Post processing framework and UI
- Fix gateway timeout not triggering failure in processing

</details>

---

### Card 28: Team Permissions and Project Privacy

**Make projects private, add team members with specific roles, and create public read-only projects for sharing.**

Effort: **M** | Items: 5 | Areas: Permissions/Auth

*Status: 2 new*

**User Stories:**

- As a project manager, I want to make my project private until data verification is complete, so unvetted results don't get shared prematurely
- As a field ecologist, I want to add collaborators as viewers or editors, so they can see results without accidentally changing settings
- As a taxonomist, I want to make a finalized project public as read-only, so other researchers can explore our verified dataset

<details>
<summary>Underlying items (5)</summary>

- Implement Private projects (MVP feature)
- Use Roles system to hide/show features and default ordering
- Multiple projects & users
- Make it clear who contacts are for each project (the initiator and the hands-on/technical contacts)
- Allow inviting a collaborator to confirm IDs

</details>

---

## SOMEDAY — Nice to Have

### Card 29: Connect to global biodiversity networks

**Share observations with GBIF, iNaturalist, Zenodo and other research platforms.**

Effort: **XL** | Items: 15 | Areas: Data-Management, Export/Interop, ML/AI, Permissions/Auth, Taxonomy

*Status: No external integrations exist. Needs API connectors, metadata mapping, OAuth, and data validation.*

**User Stories:**

- As a field ecologist, I want to publish verified observations to GBIF so that they contribute to global biodiversity databases
- As a researcher, I want to export data with DOIs so that my datasets are citable
- As a taxonomist, I want to cross-reference with iNaturalist so that I can validate rare species identifications

<details>
<summary>Underlying items (15)</summary>

- Size estimator with annotations (from normal photos, verified in Bold, iNat)
- Use iNaturalist (for validation/privacy) and Creative Commons as benchmarks
- Assign it the night before who will be doing it (Demo)
- Integrate support for barcode bin numbers for species without traditional names
- Implement querying images for inference from ADC API and POSTing results back
- Plan for an R package to interface the API for plots stats etc.
- Implement connection to GBIF (MVP feature)
- Which deployments which data are published to GBIF
- Michael to assist with data exports for new paper
- Suggests Zenodo for dataset publishing
- Integrate or share data between software and ARISE
- Publishing Zenodo DOI
- Button to publish a single observation to iNaturalist?
- Create a user for each model on iNaturalist?
- Implement fine-grained Job Permissions based on job types (e.g., ML, export, sync)

</details>

---

### Card 30: Enable citizen science participation

**Open platform to volunteers with training materials, community forums, and structured onboarding.**

Effort: **XL** | Items: 58 | Areas: Community, Data-Management, Infrastructure, Onboarding, UI/UX

*Status: Platform requires manual user creation. No public signup, forums, training materials, or volunteer workflows.*

**User Stories:**

- As a community member, I want to help identify species in my region so that I can contribute to conservation
- As a project manager, I want to invite volunteers with training materials so that they can annotate accurately
- As a new user, I want interactive tutorials so that I can learn Antenna without scheduled training

<details>
<summary>Underlying items (58)</summary>

- Citizen science page with a downloadable button
- Discussion Collections terminology
- Need tooltips? Walkthrough dialogs?
- Full support for current research projects before self-service for public
- Self-service ready? (Out of BETA officially)
- Transition public "Sign-Up" buttons to "Contact Us"
- Help organizing & auditing the panama BCI projects
- Use modularity to help divide ownership
- Help with processing of samples (since the feature is not stable enough yet)
- Get contribution agreements in writing
- Define how credit will be given
- Decide on the platform name
- Online platform for ML-assisted monitoring of arthropods (Agile software pipeline new algorithms/research friendly/efficient UI)
- Implement sustainable business/partner model
- Functionality needs for specific projects (General Topic)
- Assign and train a person at each partner org (Insectarium)
- Assigning someone from Antenna to be the main contact for each project
- Enforcing the use of the antenna email and add relevant people as recipients
- Regular call for all partners using Antenna
- Sending out a form to be filled out before each meeting
- Find project & partner manager for Antenna
- Training others to respond to partners
- Find intern and train on basic tasks
- Training sessions for our own staff
- Sustainability leadership and financial model
- Getting anxious for something to be working & finished soon
- Formalize Strategic Direction: Hosted Platform vs. Enterprise Portals vs. Open Source Only
- Formally select Option A (Client Portals) as the Q1 Strategic Alignment goal (based on lean team)
- Create a user matrix and a feature matrix (for Jan 27th meeting)
- Define Milestones for 2026 (What do we want by April/July?)
- Keep track of email correspondence with current and new contacts
- New release on GitHub
- Add to Wildlabs inventory
- Mailing list & regular updates
- Planning for meetings (accounted for)
- A side goal of the platform is to increase engagement in the observation of insects.
- Enable & expedite new formal research.
- Provide an interface for citizen scientists to learn & contribute.
- Monetization strategy/pricing (to put into grants)
- Continue to foster platform's openness and potential for collaboration
- Need for continuous funding to maintain and expand monitoring projects
- Mandatory Decision: Direction of platform (Client portals vs Central platform)
- Citizen Science Version/Features
- Place for users to add their experience
- Platform Vision/Strategy (defining goals & milestones for 2026)
- Which features before April 2026?
- Which need to be self service from a centrally hosted platform?
- Which need a planning & prototype sprint
- Which features are MVP vs production-ready?
- Which features need to be self-service vs admin-only?
- Are we trying to make an app for everyone? Supporting 2-3 partners?
- Simplicity vs. feature richness
- Which partner types? Which partner types need self-service?
- NRCAN (government/landscape scale) - custom deployment with support?
- Mothitor project/Maxim's projects (research labs) - self-service priority
- LepiNoc (citizen science) - different requirements/mobile app
- Which features empower & accelerate teams in what they already do?
- Project manager

</details>

---

### Card 31: Advanced ML research methods

**Few-shot learning, explainability, uncertainty quantification, and handling cryptic species.**

Effort: **XL** | Items: 15 | Areas: ML/AI, Research

*Status: Basic classification works. Uncertainty methods, adapters, and explainability are research prototypes only.*

**User Stories:**

- As an ML researcher, I want to test few-shot adapters so that I can add rare species without full retraining
- As a taxonomist, I want to see confusion matrices so that I understand which species pairs the model struggles with
- As a field ecologist, I want calibrated confidence scores so that I know when to trust predictions

<details>
<summary>Underlying items (15)</summary>

- Model suggestions for impossible-to-ID species (confusion matrix) and handling of cryptic species split geographically
- How can we get to research grade automatically? For the ones we can
- LORA adapter that is trained on a small amount of data and appended at inference time for improving results
- Model zoo for insects
- Is Antenna a model zoo? Or just an index of what registered & available
- Working on the "secret sauce" methods to improve results for insects - external stats
- Priors and adding statistical models (Logistic binning Shannon entropy)
- Identify "Tricky" species (cannot identify the species with visual information only)
- Transparency: How many images and what images was the model trained on?
- Transparency: We don't know about this species
- Transparency: What are the stupid errors
- Dataset transparency (show training data species/images for each model)
- Build a retraining workflow (use verified data to improve model)
- Few-shot learning for adding species
- Explainable AI - What features did you use to ID this species? Teaching the user.

</details>

---

### Card 32: Cloud deployment and multi-tenant architecture

**Scale to cloud platforms with support for thousands of concurrent projects.**

Effort: **XL** | Items: 6 | Areas: Infrastructure

*Status: Runs locally with Docker Compose. Cloud deployment is manual, not documented for SaaS multi-tenancy.*

**User Stories:**

- As a platform admin, I want to deploy on AWS so that I can serve multiple organizations without local servers
- As a new user, I want fast processing even when many jobs are running so that I don't wait days for results
- As a self-hosted user, I want Kubernetes deployment docs so that I can run Antenna at scale

<details>
<summary>Underlying items (6)</summary>

- Implement Optimizations for speed (MVP feature)
- Need consumer service to scale up (Suggested: Rodrigo)
- Investigate/Implement containerisation for massively parallel (10000 core+) image processing
- Move to managed hosting (if centralized system is desired)
- Explore Kubernetes if limited by Docker Swarm
- Switch background tasks from long running to many short

</details>

---

### Card 33: Expand beyond moth camera traps

**Support acoustic monitoring, pollinators, microscope images, and non-time-series data.**

Effort: **XL** | Items: 6 | Areas: Data-Management, ML/AI, Permissions/Auth, Research, UI/UX

*Status: Platform is designed for nighttime moth camera traps only. No support for other monitoring modes.*

**User Stories:**

- As a field ecologist, I want to upload bat detector audio so that I can analyze acoustic data alongside images
- As a researcher, I want to process daytime pollinator surveys so that I can study bee and butterfly diversity
- As a taxonomist, I want to digitize museum drawers so that I can analyze pinned specimen images

<details>
<summary>Underlying items (6)</summary>

- Labs page - Inference app and butterfly experiment
- Distinguish between no more fine-grained labels available and need for more information to label prediction limitations
- Other invertebrates - other nocturnals, and day-time polinators
- Labeling behavior poses and other attributes
- Implement same data process for acoustic recordings
- Implement multi-level (Curator expert etc.) point-based validation/curation (eButterfly model)

</details>

---

### Card 34: Measure biomass and track individuals

**Estimate insect size and biomass, track individuals across frames to measure abundance accurately.**

Effort: **XL** | Items: 7 | Areas: Analytics/Viz, Data-Management, DevEx, Infrastructure, ML/AI, Research

*Status: Bounding boxes exist. Size estimation and tracking are research prototypes. Segmentation not implemented.*

**User Stories:**

- As a field ecologist, I want to estimate biomass per night so that I can measure ecosystem health trends
- As an ML researcher, I want to track individuals across frames so that I don't double-count occurrences
- As a researcher, I want physical size in centimeters so that I can study body size distributions

<details>
<summary>Underlying items (7)</summary>

- See detections grouped as tracks (UI and data structures prepared, logic in progress)
- Bug: Counts per deployment
- Demo other segmentation algorithms
- Estimation of physical size. Biomass.
- Tracking of individuals (deduplication)
- Everything related to the infrastructure (accounted for)
- Continuing to make tickets in ami-admin repo and track ongoing projects

</details>

---

### Card 35: Multi-level validation and curation

**Structured expert review, flagging tools, consensus workflows, and data quality assurance.**

Effort: **L** | Items: 10 | Areas: Data-Management, Research, UI/UX

*Status: Basic ID UI exists. No structured multi-level review, flagging workflows, or QC dashboards.*

**User Stories:**

- As a taxonomist, I want to flag detections for specialist review so that difficult IDs go to the right expert
- As a project manager, I want to track validation progress so that I know which groups need attention
- As a field ecologist, I want to mark observations as 'not identifiable' so that I don't waste time

<details>
<summary>Underlying items (10)</summary>

- Not identifiable based on current image quick action
- Incorrect (based on my knowledge) quick reaction
- Provide a list of species to choose from for validation/annotation
- Provide a mechanism for regional experts to flag instances for further investigation
- Quick flagging
- Software incorrectly ID'd moss/bark as moth species with no way to report
- Concern about handling incorrect timestamps from faulty real-time clocks
- Plan to review data only at end of deployment
- Define the Validation protocol and how to reach research-grade
- Quality control of every stage before & after processing

</details>

---

### Card 38: Advanced ML models and regional coverage

**Better detectors, regional models, genus-level classification, and handling of overlapping specimens.**

Effort: **XL** | Items: 12 | Areas: ML/AI

*Status: Basic detector and classifier work. Regional models exist for some areas. Segmentation is prototype only.*

**User Stories:**

- As an ML researcher, I want segmentation detectors so that I can handle overlapping moths
- As a field ecologist in Costa Rica, I want a regional model so that predictions are tuned to local species
- As a taxonomist, I want genus-level predictions when species ID is impossible so that I get useful coarse labels

<details>
<summary>Underlying items (12)</summary>

- Implement Better algorithms (MVP feature)
- ML backend (General Topic)
- Improving quality of results - and what gets an ID at all
- Multiple objects in one bounding box
- Demo Flatbug
- Somehow display which species the model is better or worse at
- Re-training panama model with fewer
- How to do process efficiently in batch (similarity model, etc)
- All arthropods model (global insects, spiders, etc)
- Continue to maintain and enhance the integration of multiple algorithms for species identification
- Allow ability to resume job where it failed
- Test semi-automated training (active learning) of models

</details>

---

## SOMEDAY — Nice to Have

### Card 36: Platform maturity and strategic vision

**Internationalization, API clients, business model, branding, and long-term sustainability planning.**

Effort: **XL** | Items: 87 | Areas: Analytics/Viz, Data-Management, DevEx, Documentation, Infrastructure, Onboarding, Permissions/Auth, Research, Taxonomy, UI/UX

*Status: English-only, no official API clients, no revenue model, minimal branding. Needs strategic planning.*

**User Stories:**

- As a researcher in Latin America, I want Antenna in Spanish so that my team can collaborate effectively
- As a data scientist, I want an R client so that I can integrate Antenna into my analysis pipelines
- As a platform admin, I want a sustainable business model so that Antenna continues long-term

<details>
<summary>Underlying items (87)</summary>

- I personally can not ID this quick action
- Add multilingual localization support
- Represent Antenna UI in Figma (for high fidelity prototyping)
- Clear distinction for "3rd party" vs. certified models (Antenna logo!)
- More prototypes
- Getting user personas and user stories on paper
- Transition Sign-Up buttons to Contact Us (Strategic)
- Experimenting with fine-grained classification
- Importance of long-term data for ecological and taxonomic research
- Ability to demo models & techniques more easily (without setting up a research project) - Focus on internal use
- Automating the current interface (prototype)
- Python & R clients to interact with data already in Antenna
- ML Developer & researcher experience for improving ML
- Michael to assist with technical description of methods for new paper
- Updated diagrams for presentations in October
- Mind map of what's to come after this
- Difficulty with command-line interfaces and IT restrictions
- Document full vision of complete AMI solution at scale
- Add processing support for project data
- Record if the suggestion was manually typed or accepted from a proposition
- Citation information
- Expose info about which model and when for each machine ID
- Data connector tool
- Add panama trap IDs
- Processing all data once model is ready & agreed on
- Adding clear description to each project
- Needs to be put in a boxe
- Wipe them
- Rename the files (Anna)
- Sample the files (Anna)
- 10 minutes intervals (Sampling)
- Charge batteries
- Filtering bad data (too small too blurry)
- Copying projects
- Use hierarchical folders for organizing cropped images by taxonomic order and family
- Add more fields for detailed hardware information
- Change 'Captures per hour' to 'Average captures per hour per night'
- Change 'Detections per hour' to 'Detections per hour per night on average'
- Summary metrics - species richness. The accuracy of the species richness is 90% even when the classification accuracy is 60%.
- Summary shows capture/hr and sessions/month - suggest other relevant data
- Register existing projects and process 2 years of data (Next 6 months)
- Geofencing
- Image classifier from infrared or hyper-spectral images
- Fast object detector edge deployments
- How can we confidently scale these systems beyond what humans can do?
- Common challenges - two lists of classes: species that exist and species that you can identify visually from a top-down image.
- Is this any more efficient than traditional monitoring
- Do we really need a species level classifier? For which species? For which purposes?
- Building a dataset of moth size information
- Ask Chris for list of any, all categories of interest
- Analyze morphological traits and temporal patterns, using the data we have
- What can we do with the data we have?
- Comparison with traditional monitoring data (BCI)
- Clearly define the issues we see
- Propose projects to work on new methods
- Skeptical about speed and accuracy of integrating DNA barcoding data
- Ensure platform interoperability trap agnostic and modular design
- Use JASMIN for storage
- Focus on hardening (stability fixes speed) Processing fixing gaps in workflow
- Upgrade Node.js?
- Split up backend modules
- Processing speed & stability (switch to producer/consumer model)
- Capturing data (sending direct to antenna)
- Antenna (self-hosted version)
- Standardizing the model APIs
- Support for per-bucket permissions for S3/Swift keys
- Allow more CEPHFS shares
- Transition to automated and centralized instance management
- h265 encoding with regional resolution
- Email sending
- Processing stabilization
- Merge PRs - project ID filter
- Switch to a JS framework in 2026
- Split up backend modules
- Complete migration of UI components from raw Radix primitives to shadcn/ui
- Complete migration from style modules to Tailwind CSS
- Move UI kit back to Antenna repo
- Migrate to React 19
- Migrate to Next.js (simplify routing and code splitting)
- Upgrade Node.js
- Taxonomy API & shared database
- Ask Chris for list of any all categories of interest
- How much freedom do we give projects & users for Taxonomy
- Obfuscating exact device location (Sensitive/Fuzzy privacy)
- Orgs & Per-project permissions (Mohamed's work)
- Allow users to invite categories
- Support for application tokens that are not tied to a specific user

</details>

---

### Card 37: UI polish and usability improvements

**Minor UI fixes, tooltips, better defaults, keyboard shortcuts, and incremental UX enhancements.**

Effort: **M** | Items: 31 | Areas: UI/UX

*Status: Core UI functional. Many small polish items remain as tech debt or 'nice-to-haves'.*

**User Stories:**

- As a new user, I want helpful tooltips so that I understand features without reading docs
- As a field ecologist, I want better default filters so that I see relevant results immediately
- As a taxonomist, I want the interface to remember my preferences so that I don't reconfigure every session

<details>
<summary>Underlying items (31)</summary>

- Implement date filtering
- Display projects user is part of/manager of in My Antenna
- Display user's focused species in My Antenna
- Never identifiable based on image quick action
- Family/genus/tribe correct quick reaction
- Show Num Captures column under deployments.
- Don't show Not a Moth by default (need project setting for these special Taxon)
- Bug: Cluster cover images are not automatically set
- Should always be encouraging and pleasurable to use.
- Clarify indication for unprocessed collections
- Connect comments box
- Clarify saving changes (automatic vs. manual)
- Back button should retain selected filters
- Make filters more visible for intuitive understanding
- Make thumbnails clickable
- Auto-refresh image after single image job completion
- Continue to maintain the ability to see detailed information about captured images
- Continue to maintain the clean interface of the software
- Continue to maintain the intuitive navigation and user-friendly interface
- Make some interface elements like the filter bar fixed
- Expose deployment drop-down when registering a new job
- Auto-open status modal when single job is started
- Filters vs project settings
- Idea on how to disable filters
- Ability to delete a site/pipeline/or device type
- Search project option on the main page
- Register new project button hard to find
- Pipeline tag isn't really clear
- Image illustrating projects should be scaled to the size of rectangular window
- Regex null bug (UI gap)
- Regex null bug

</details>

---

## DONE — Capability Inventory (109 items)

These features are already built. Useful context for the team to understand what exists.
See `roadmap-master.csv` for the full list of completed items.
