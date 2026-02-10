# Antenna Roadmap — Meeting Board Cards

Generated from 754 roadmap items distilled across 12+ planning documents, working group meetings,
field notes, and GitHub activity. Cards are themed top-down from the strategic analysis in
`roadmap-distillation-plan.md`, not clustered bottom-up from item text.

## How to Use These Cards

**Meeting format:** FigJam board with sticky notes. Two activities:
1. **Partner prioritization** — which partner projects to commit to for complete case studies
2. **Feature prioritization** — drag cards between Now / Maybe / Never columns

**Audience:** Ecologists, ML researchers, project managers, and upper management.
Cards are written in plain language. Technical detail is in the collapsible item lists.

---

**Total items mapped:** 735 of 754

## Now (Next 3 Months) — 17 cards, 166 items

_Actionable cards for the immediate sprint. These need partner input to finalize priority order._

### Project Quick Start

_Let new users go from 'I have images' to 'I see results' in minutes with a single guided form._

**Effort:** L | **Items:** 19 | **Status:** 19 untracked

**User stories:**
- As a new user at a conference, I want to upload sample images and see results immediately so I know if Antenna works for my data.
- As a field ecologist, I want to create a project with minimal setup so I can evaluate the platform quickly.
- As a project manager, I want a demo project that showcases the platform's capabilities to potential partners.

<details>
<summary>Underlying items (19)</summary>

- ❌ Ready for seamless live demonstrations
- ❌ Implement Project Quick Start feature (MVP for auto-creating draft projects and processing data)
- ❌ Quickstart designs/project (Create a quick start project)
- ❌ Quick start project / demo
- ❌ Design stable & streamlined workflow: Get from Cameras to moths with few steps
- ❌ All-in-one test page
- ❌ Sign up on the platform waitlist
- ❌ Sign up as new user on the platform (Currently disabled manually add new users)
- ❌ Create a project from scratch (Currently disabled for most users soon enabled for all)
- ❌ Sign up as new user (currently requires admin support)
- ❌ Account Sign-ups (Self-service feature remaining, currently requires admin support)
- ❌ Onboarding Flow (Centrally Managed Antenna & UI flow)
- ❌ Create a project from scratch (Partially implemented/disabled for most)
- ❌ Scratch/draft project based on images (upload a folder)
- ❌ Feature Rollout: Create a project from scratch is partially implemented
- ❌ New project Wizard
- ❌ Create a project from scratch
- ❌ Self-service features (using feature-flags/complexity as opt-in)
- ❌ Create a project from scratch (Partially implemented)

</details>

### Data Upload and Import

_Upload images from cameras and import externally processed data without developer help._

**Effort:** L | **Items:** 19 | **Status:** 6 tracked in GitHub; 12 partially implemented; 1 untracked

**User stories:**
- As a field ecologist, I want to upload images from my camera's SD card to the platform without command-line tools.
- As a project manager, I want to import detection results from another system so I can use Antenna for verification and analysis.

<details>
<summary>Underlying items (19)</summary>

- 🔧 Reworking collections - clarifying & solidifying dynamic filters vs. fixed datasets (x4) [[#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [PR#895](https://github.com/AMI-system/antenna/pull/895)(MERGED); [PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED)]
- 🔧 Data uploader (Technician) (x2) [[PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#909](https://github.com/AMI-system/antenna/pull/909)(MERGED); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN)]
- 🔧 Collaborate on data uploader and image database [[PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#928](https://github.com/AMI-system/antenna/issues/928)(OPEN); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED)]
- 🔧 Manual image uploading from UI or background sync of large datasets [[PR#584](https://github.com/AMI-system/antenna/pull/584)(MERGED); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#895](https://github.com/AMI-system/antenna/pull/895)(MERGED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#614](https://github.com/AMI-system/antenna/issues/614)(CLOSED)]
- 🔧 Desktop data uploading tool [[PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#909](https://github.com/AMI-system/antenna/pull/909)(MERGED); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [#789](https://github.com/AMI-system/antenna/issues/789)(CLOSED)]
- 🔧 Need a way to upload a bunch of images without full config [[PR#909](https://github.com/AMI-system/antenna/pull/909)(MERGED); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#314](https://github.com/AMI-system/antenna/issues/314)(CLOSED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED)]
- 📋 Antenna Go - offline mobile companion app [[#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#757](https://github.com/AMI-system/antenna/issues/757)(OPEN); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [#808](https://github.com/AMI-system/antenna/issues/808)(CLOSED); [#485](https://github.com/AMI-system/antenna/issues/485)(CLOSED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [PR#983](https://github.com/AMI-system/antenna/pull/983)(MERGED)]
- 📋 Easy desktop application for uploading data from machines to Antenna [[#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#757](https://github.com/AMI-system/antenna/issues/757)(OPEN); [PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#1078](https://github.com/AMI-system/antenna/issues/1078)(CLOSED); [PR#983](https://github.com/AMI-system/antenna/pull/983)(MERGED)]
- 📋 Enhance user experience for large image uploads through integration with cloud services [[#910](https://github.com/AMI-system/antenna/issues/910)(OPEN); [#1089](https://github.com/AMI-system/antenna/issues/1089)(OPEN); [PR#202](https://github.com/AMI-system/antenna/pull/202)(MERGED); [#226](https://github.com/AMI-system/antenna/issues/226)(CLOSED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [PR#112](https://github.com/AMI-system/antenna/pull/112)(MERGED); [PR#111](https://github.com/AMI-system/antenna/pull/111)(MERGED); [PR#921](https://github.com/AMI-system/antenna/pull/921)(MERGED); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED)]
- 📋 Online/Offline functionality [[#676](https://github.com/AMI-system/antenna/issues/676)(CLOSED); [#538](https://github.com/AMI-system/antenna/issues/538)(OPEN); [#766](https://github.com/AMI-system/antenna/issues/766)(OPEN)]
- 📋 Antenna Lite - mobile app for moth traps that automatically registers an annoynmous station [[#439](https://github.com/AMI-system/antenna/issues/439)(OPEN); [#418](https://github.com/AMI-system/antenna/issues/418)(CLOSED); [#419](https://github.com/AMI-system/antenna/issues/419)(OPEN); [PR#227](https://github.com/AMI-system/antenna/pull/227)(MERGED); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [PR#231](https://github.com/AMI-system/antenna/pull/231)(MERGED); [#958](https://github.com/AMI-system/antenna/issues/958)(OPEN); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#1002](https://github.com/AMI-system/antenna/pull/1002)(MERGED)]
- 📋 Resizing images for the app (use prisma urls in API response) [[#419](https://github.com/AMI-system/antenna/issues/419)(OPEN); [#729](https://github.com/AMI-system/antenna/issues/729)(OPEN); [PR#231](https://github.com/AMI-system/antenna/pull/231)(MERGED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [#593](https://github.com/AMI-system/antenna/issues/593)(OPEN); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#146](https://github.com/AMI-system/antenna/pull/146)(MERGED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [PR#688](https://github.com/AMI-system/antenna/pull/688)(MERGED); [PR#348](https://github.com/AMI-system/antenna/pull/348)(MERGED)]
- 🔧 Importing - Captures (import a list of public HTTP urls) (x2) [[PR#203](https://github.com/AMI-system/antenna/pull/203)(MERGED); [PR#292](https://github.com/AMI-system/antenna/pull/292)(MERGED); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED); [PR#838](https://github.com/AMI-system/antenna/pull/838)(MERGED); [#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [#393](https://github.com/AMI-system/antenna/issues/393)(CLOSED); [#998](https://github.com/AMI-system/antenna/issues/998)(CLOSED); [PR#247](https://github.com/AMI-system/antenna/pull/247)(MERGED); [#984](https://github.com/AMI-system/antenna/issues/984)(CLOSED); [#1037](https://github.com/AMI-system/antenna/issues/1037)(OPEN)]
- 🔧 Develop a Data connector app (MVP feature) [[PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#983](https://github.com/AMI-system/antenna/pull/983)(MERGED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [#485](https://github.com/AMI-system/antenna/issues/485)(CLOSED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [#1078](https://github.com/AMI-system/antenna/issues/1078)(CLOSED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#918](https://github.com/AMI-system/antenna/pull/918)(MERGED); [PR#688](https://github.com/AMI-system/antenna/pull/688)(MERGED); [#1106](https://github.com/AMI-system/antenna/issues/1106)(OPEN)]
- 🔧 Continue to maintain filename format check for manual uploads [[PR#909](https://github.com/AMI-system/antenna/pull/909)(MERGED); [PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [#878](https://github.com/AMI-system/antenna/issues/878)(OPEN); [#687](https://github.com/AMI-system/antenna/issues/687)(OPEN); [#562](https://github.com/AMI-system/antenna/issues/562)(OPEN); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#242](https://github.com/AMI-system/antenna/issues/242)(CLOSED); [PR#1114](https://github.com/AMI-system/antenna/pull/1114)(MERGED); [PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)]
- 🔧 Importing already-processed data into Antenna [[PR#203](https://github.com/AMI-system/antenna/pull/203)(MERGED); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED); [PR#838](https://github.com/AMI-system/antenna/pull/838)(MERGED); [PR#292](https://github.com/AMI-system/antenna/pull/292)(MERGED); [#998](https://github.com/AMI-system/antenna/issues/998)(CLOSED); [#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [#393](https://github.com/AMI-system/antenna/issues/393)(CLOSED); [#703](https://github.com/AMI-system/antenna/issues/703)(CLOSED); [#984](https://github.com/AMI-system/antenna/issues/984)(CLOSED); [#625](https://github.com/AMI-system/antenna/issues/625)(OPEN)]
- 🔧 Upload data to the storage (desktop app) (Currently happens outside Antenna using tools like Cyberduck) [[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [PR#231](https://github.com/AMI-system/antenna/pull/231)(MERGED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#146](https://github.com/AMI-system/antenna/pull/146)(MERGED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#593](https://github.com/AMI-system/antenna/issues/593)(OPEN); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED)]
- ❌ Implement drag and drop feature for manual uploads (x2)
- 🔧 Non-timeseries data - Microscopy & field photos [[#308](https://github.com/AMI-system/antenna/issues/308)(CLOSED); [PR#186](https://github.com/AMI-system/antenna/pull/186)(MERGED); [#625](https://github.com/AMI-system/antenna/issues/625)(OPEN); [PR#781](https://github.com/AMI-system/antenna/pull/781)(MERGED); [PR#1105](https://github.com/AMI-system/antenna/pull/1105)(MERGED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#905](https://github.com/AMI-system/antenna/pull/905)(MERGED); [PR#829](https://github.com/AMI-system/antenna/pull/829)(MERGED); [PR#809](https://github.com/AMI-system/antenna/pull/809)(MERGED)]

</details>

### Pipeline and Model Management

_Configure, deploy, and manage ML pipelines — model registry, processing service UI, reprocessing, active/inactive pipelines._

**Effort:** L | **Items:** 16 | **Status:** 2 tracked in GitHub; 14 partially implemented

**User stories:**
- As a project manager, I want to choose which ML pipelines run on my data without developer help.
- As an ML researcher, I want to register new models and track their lineage in the platform.

<details>
<summary>Underlying items (16)</summary>

- 🔧 Display species lists known by each model [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED)]
- 🔧 Expose more details about each pipeline (ID URL version) in customizable pipelines feature [[PR#680](https://github.com/AMI-system/antenna/pull/680)(CLOSED); [#677](https://github.com/AMI-system/antenna/issues/677)(CLOSED); [#309](https://github.com/AMI-system/antenna/issues/309)(CLOSED); [PR#1117](https://github.com/AMI-system/antenna/pull/1117)(OPEN); [#1076](https://github.com/AMI-system/antenna/issues/1076)(OPEN); [PR#1011](https://github.com/AMI-system/antenna/pull/1011)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#1053](https://github.com/AMI-system/antenna/pull/1053)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED)]
- 🔧 Add active/inactive field for pipelines show inactive pipelines below and make them unselectable for new data processing [[#677](https://github.com/AMI-system/antenna/issues/677)(CLOSED); [#309](https://github.com/AMI-system/antenna/issues/309)(CLOSED); [PR#1117](https://github.com/AMI-system/antenna/pull/1117)(OPEN); [#1076](https://github.com/AMI-system/antenna/issues/1076)(OPEN); [PR#1011](https://github.com/AMI-system/antenna/pull/1011)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#1053](https://github.com/AMI-system/antenna/pull/1053)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#1041](https://github.com/AMI-system/antenna/pull/1041)(MERGED)]
- 🔧 Make Access Key for pipelines visible (not a password field) [[PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#921](https://github.com/AMI-system/antenna/pull/921)(MERGED); [PR#1035](https://github.com/AMI-system/antenna/pull/1035)(OPEN); [PR#964](https://github.com/AMI-system/antenna/pull/964)(OPEN); [PR#880](https://github.com/AMI-system/antenna/pull/880)(OPEN); [PR#1117](https://github.com/AMI-system/antenna/pull/1117)(OPEN); [#1110](https://github.com/AMI-system/antenna/issues/1110)(OPEN); [PR#1101](https://github.com/AMI-system/antenna/pull/1101)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#1096](https://github.com/AMI-system/antenna/pull/1096)(OPEN)]
- 📋 Implement Flatbug and AMBER models [[#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)]
- 🔧 ML processing done via web API support for any language or framework [[PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED); [#1110](https://github.com/AMI-system/antenna/issues/1110)(OPEN); [#1052](https://github.com/AMI-system/antenna/issues/1052)(OPEN); [#1010](https://github.com/AMI-system/antenna/issues/1010)(OPEN); [PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#693](https://github.com/AMI-system/antenna/pull/693)(MERGED); [#875](https://github.com/AMI-system/antenna/issues/875)(OPEN)]
- 🔧 Model registry links to experiment details in WandB [[PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [#758](https://github.com/AMI-system/antenna/issues/758)(CLOSED)]
- 🔧 Additional ML backends [[PR#312](https://github.com/AMI-system/antenna/pull/312)(MERGED); [PR#190](https://github.com/AMI-system/antenna/pull/190)(MERGED); [PR#189](https://github.com/AMI-system/antenna/pull/189)(MERGED); [PR#180](https://github.com/AMI-system/antenna/pull/180)(MERGED); [#515](https://github.com/AMI-system/antenna/issues/515)(OPEN); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED)]
- 🔧 Deploy some of Kat's models to a server [[PR#1007](https://github.com/AMI-system/antenna/pull/1007)(MERGED); [PR#312](https://github.com/AMI-system/antenna/pull/312)(MERGED); [#414](https://github.com/AMI-system/antenna/issues/414)(CLOSED)]
- 🔧 Improving the results [[#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#679](https://github.com/AMI-system/antenna/pull/679)(OPEN)]
- 🔧 Configure processing services for a project [[PR#1117](https://github.com/AMI-system/antenna/pull/1117)(OPEN); [PR#1011](https://github.com/AMI-system/antenna/pull/1011)(OPEN); [PR#1053](https://github.com/AMI-system/antenna/pull/1053)(MERGED); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#768](https://github.com/AMI-system/antenna/pull/768)(MERGED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [PR#736](https://github.com/AMI-system/antenna/pull/736)(MERGED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#715](https://github.com/AMI-system/antenna/pull/715)(MERGED); [PR#705](https://github.com/AMI-system/antenna/pull/705)(MERGED)]
- 🔧 Reprocessing detections with a new classifier [[PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED); [PR#706](https://github.com/AMI-system/antenna/pull/706)(CLOSED)]
- 🔧 Review current models (trained when, checklists) [[PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED)]
- 🔧 Processing pipeline for analyzing individual images [[#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#1053](https://github.com/AMI-system/antenna/pull/1053)(MERGED); [PR#1033](https://github.com/AMI-system/antenna/pull/1033)(MERGED); [PR#949](https://github.com/AMI-system/antenna/pull/949)(MERGED); [PR#921](https://github.com/AMI-system/antenna/pull/921)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [#982](https://github.com/AMI-system/antenna/issues/982)(OPEN); [PR#938](https://github.com/AMI-system/antenna/pull/938)(OPEN)]
- 🔧 Use the zero-shot model [[PR#1007](https://github.com/AMI-system/antenna/pull/1007)(MERGED)]
- 📋 Model Management (model orchestration & revision/deploying new models) [[PR#386](https://github.com/AMI-system/antenna/pull/386)(OPEN)]

</details>

### Fix Critical Bugs

_Resolve trust-killing issues: password reset, dangling jobs, processing failures, and milestone #27 items._

**Effort:** L | **Items:** 15 | **Status:** 4 tracked in GitHub; 7 partially implemented; 4 untracked

**User stories:**
- As a user, I want to reset my password without contacting a developer so I can recover my account independently.
- As a project manager, I want processing jobs to complete reliably without hanging indefinitely.
- As any user, I want basic platform operations to work consistently so I can trust the system with my research.

<details>
<summary>Underlying items (15)</summary>

- ❌ Fix critical issues with processing service API (milestone #27)
- 🔧 Run a ML job (Unstable, jobs stop, status not reflected correctly, crops not saved, not all captures processed) [[#404](https://github.com/AMI-system/antenna/issues/404)(CLOSED); [PR#286](https://github.com/AMI-system/antenna/pull/286)(MERGED); [#1059](https://github.com/AMI-system/antenna/issues/1059)(OPEN); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [PR#937](https://github.com/AMI-system/antenna/pull/937)(MERGED); [#1025](https://github.com/AMI-system/antenna/issues/1025)(OPEN); [PR#919](https://github.com/AMI-system/antenna/pull/919)(MERGED); [#922](https://github.com/AMI-system/antenna/issues/922)(OPEN)]
- 🔧 Processing and job failing [[#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [PR#303](https://github.com/AMI-system/antenna/pull/303)(MERGED); [#404](https://github.com/AMI-system/antenna/issues/404)(CLOSED); [PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [PR#268](https://github.com/AMI-system/antenna/pull/268)(MERGED); [PR#919](https://github.com/AMI-system/antenna/pull/919)(MERGED); [#1072](https://github.com/AMI-system/antenna/issues/1072)(CLOSED); [#922](https://github.com/AMI-system/antenna/issues/922)(OPEN); [#782](https://github.com/AMI-system/antenna/issues/782)(CLOSED); [PR#368](https://github.com/AMI-system/antenna/pull/368)(MERGED)]
- 🔧 Processing Bugs (processing jobs stalling/status updates incorrect) [[#721](https://github.com/AMI-system/antenna/issues/721)(OPEN); [PR#1062](https://github.com/AMI-system/antenna/pull/1062)(MERGED); [PR#934](https://github.com/AMI-system/antenna/pull/934)(MERGED); [#773](https://github.com/AMI-system/antenna/issues/773)(CLOSED); [#1072](https://github.com/AMI-system/antenna/issues/1072)(CLOSED); [PR#554](https://github.com/AMI-system/antenna/pull/554)(MERGED); [PR#946](https://github.com/AMI-system/antenna/pull/946)(MERGED); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [PR#178](https://github.com/AMI-system/antenna/pull/178)(MERGED); [PR#1051](https://github.com/AMI-system/antenna/pull/1051)(MERGED)]
- 📋 Bug: Sessions not automatically created after sync [[#904](https://github.com/AMI-system/antenna/issues/904)(OPEN); [#872](https://github.com/AMI-system/antenna/issues/872)(CLOSED); [PR#898](https://github.com/AMI-system/antenna/pull/898)(MERGED); [PR#1073](https://github.com/AMI-system/antenna/pull/1073)(MERGED); [PR#1051](https://github.com/AMI-system/antenna/pull/1051)(MERGED); [PR#803](https://github.com/AMI-system/antenna/pull/803)(MERGED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#387](https://github.com/AMI-system/antenna/issues/387)(CLOSED); [PR#194](https://github.com/AMI-system/antenna/pull/194)(MERGED); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN)]
- 🔧 Fix issues with timestamps not being recognized in the current format [[PR#781](https://github.com/AMI-system/antenna/pull/781)(MERGED); [#273](https://github.com/AMI-system/antenna/issues/273)(OPEN); [PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [#398](https://github.com/AMI-system/antenna/issues/398)(OPEN); [#233](https://github.com/AMI-system/antenna/issues/233)(CLOSED); [#723](https://github.com/AMI-system/antenna/issues/723)(CLOSED); [PR#644](https://github.com/AMI-system/antenna/pull/644)(MERGED); [#462](https://github.com/AMI-system/antenna/issues/462)(CLOSED); [PR#1105](https://github.com/AMI-system/antenna/pull/1105)(MERGED)]
- 🔧 Sample captures only valid when image file name is in YYYYMMDDHHMMSS format [[PR#326](https://github.com/AMI-system/antenna/pull/326)(MERGED); [PR#187](https://github.com/AMI-system/antenna/pull/187)(MERGED); [#1037](https://github.com/AMI-system/antenna/issues/1037)(OPEN); [#229](https://github.com/AMI-system/antenna/issues/229)(OPEN); [PR#1036](https://github.com/AMI-system/antenna/pull/1036)(MERGED); [#585](https://github.com/AMI-system/antenna/issues/585)(CLOSED); [PR#162](https://github.com/AMI-system/antenna/pull/162)(MERGED); [PR#947](https://github.com/AMI-system/antenna/pull/947)(MERGED); [PR#287](https://github.com/AMI-system/antenna/pull/287)(MERGED); [#890](https://github.com/AMI-system/antenna/issues/890)(OPEN)]
- 🔧 Data Integrity Issues (sessions not auto-created/null in data sync view) [[#549](https://github.com/AMI-system/antenna/issues/549)(CLOSED); [#793](https://github.com/AMI-system/antenna/issues/793)(OPEN); [#872](https://github.com/AMI-system/antenna/issues/872)(CLOSED); [PR#282](https://github.com/AMI-system/antenna/pull/282)(MERGED); [PR#584](https://github.com/AMI-system/antenna/pull/584)(MERGED); [PR#689](https://github.com/AMI-system/antenna/pull/689)(MERGED); [PR#898](https://github.com/AMI-system/antenna/pull/898)(MERGED); [PR#189](https://github.com/AMI-system/antenna/pull/189)(MERGED); [#879](https://github.com/AMI-system/antenna/issues/879)(OPEN); [PR#379](https://github.com/AMI-system/antenna/pull/379)(MERGED)]
- 🔧 Taxa page speed (fix in progress) and Species views (too slow) [[PR#249](https://github.com/AMI-system/antenna/pull/249)(MERGED); [PR#777](https://github.com/AMI-system/antenna/pull/777)(MERGED); [#927](https://github.com/AMI-system/antenna/issues/927)(CLOSED); [#825](https://github.com/AMI-system/antenna/issues/825)(CLOSED); [PR#828](https://github.com/AMI-system/antenna/pull/828)(MERGED); [PR#853](https://github.com/AMI-system/antenna/pull/853)(MERGED); [#831](https://github.com/AMI-system/antenna/issues/831)(CLOSED); [#264](https://github.com/AMI-system/antenna/issues/264)(CLOSED); [#1045](https://github.com/AMI-system/antenna/issues/1045)(OPEN); [PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED)]
- ❌ Consistent saving behavior (x3)
- 📋 The modal window for taxon should keep on the occurrences / other context instead of sending back to taxa list (x2) [[PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED); [#560](https://github.com/AMI-system/antenna/issues/560)(OPEN)]
- ❌ Can't update name, parents or tags
- ❌ Project ID required when changing name/tags of cluster
- 📋 Fix gateway timeout not triggering failure in processing [[PR#699](https://github.com/AMI-system/antenna/pull/699)(OPEN)]
- 📋 Fix inconsistent Processed counts in job logs [[#904](https://github.com/AMI-system/antenna/issues/904)(OPEN)]

</details>

### Species List Management

_Create, edit, and assign regional species lists to projects for class masking and result filtering._

**Effort:** L | **Items:** 13 | **Status:** 4 tracked in GitHub; 6 partially implemented; 3 untracked

**User stories:**
- As a taxonomist, I want to maintain a regional species checklist so predictions are restricted to plausible species.
- As a project manager, I want to assign different species lists to different deployments based on their location.

<details>
<summary>Underlying items (13)</summary>

- 🔧 Implement Global lists vs. Project lists for species [[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED); [#746](https://github.com/AMI-system/antenna/issues/746)(OPEN); [#871](https://github.com/AMI-system/antenna/issues/871)(OPEN)]
- ❌ Mapping species from classifier output to custom lists
- 🔧 Taxa list of support (makes it possible to filter on species of concern) [[PR#797](https://github.com/AMI-system/antenna/pull/797)(OPEN); [PR#356](https://github.com/AMI-system/antenna/pull/356)(MERGED); [#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED); [#933](https://github.com/AMI-system/antenna/issues/933)(OPEN)]
- 📋 Import the full list of species of concern [[#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#545](https://github.com/AMI-system/antenna/issues/545)(OPEN); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED)]
- 📋 Corrected species list for Panama (mainly for identification of processed data) [[#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#757](https://github.com/AMI-system/antenna/pull/757)(OPEN)]
- 🔧 Extend the list of species if needed for labellers? [[#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [#545](https://github.com/AMI-system/antenna/issues/545)(OPEN); [PR#850](https://github.com/AMI-system/antenna/pull/850)(MERGED)]
- ❌ Missing Not Identifiable class in OOD environment
- 📋 Features for 'Species watch list' / 'species of concern' (economic concern) [[#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [#545](https://github.com/AMI-system/antenna/issues/545)(OPEN)]
- 📋 Ability to configure a species list [[#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [#545](https://github.com/AMI-system/antenna/issues/545)(OPEN)]
- 🔧 Extend the list of taxa when needed (Users have to reach out when taxa are missing) [[PR#356](https://github.com/AMI-system/antenna/pull/356)(MERGED); [#1020](https://github.com/AMI-system/antenna/issues/1020)(OPEN); [#1081](https://github.com/AMI-system/antenna/issues/1081)(OPEN)]
- 🔧 Import new species & species images [[#490](https://github.com/AMI-system/antenna/issues/490)(OPEN); [#933](https://github.com/AMI-system/antenna/issues/933)(OPEN); [#871](https://github.com/AMI-system/antenna/issues/871)(OPEN); [PR#940](https://github.com/AMI-system/antenna/pull/940)(MERGED); [PR#850](https://github.com/AMI-system/antenna/pull/850)(MERGED)]
- 🔧 Taxonomy Features (adding new species/project-based taxonomy) [[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED); [#490](https://github.com/AMI-system/antenna/issues/490)(OPEN); [#746](https://github.com/AMI-system/antenna/issues/746)(OPEN)]
- ❌ Taxonomy - Mapping to algorithms (most important UI feature)

</details>

### Model Retraining for Partners

_Retrain and deploy regional models using partner-verified data to improve accuracy for specific use cases._

**Effort:** L | **Items:** 12 | **Status:** 12 partially implemented

**User stories:**
- As an ML researcher, I want to retrain the classifier on Panama-verified data so results improve for tropical species.
- As a project manager, I want a regional model tuned to my camera's data so accuracy reflects my specific conditions.

<details>
<summary>Underlying items (12)</summary>

- 🔧 Training new regional models for improving results for regional species [[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED); [#490](https://github.com/AMI-system/antenna/issues/490)(OPEN); [PR#327](https://github.com/AMI-system/antenna/pull/327)(MERGED)]
- 🔧 Questions threshold logic for family-level identifications [[PR#417](https://github.com/AMI-system/antenna/pull/417)(MERGED); [PR#241](https://github.com/AMI-system/antenna/pull/241)(MERGED)]
- 🔧 Trait analysis, temporal patterns, biomass, higher rank information, etc [[PR#712](https://github.com/AMI-system/antenna/pull/712)(MERGED); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)]
- 🔧 Size estimation (exposing in UI, centimeter calibration, incorporating into models) (x2) [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 🔧 New model for Panama (current models include P. interpunctella and v2 has a short species list) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED)]
- 🔧 Panama plus model? Needs review uses a different species list. [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#490](https://github.com/AMI-system/antenna/issues/490)(OPEN)]
- 🔧 Retrain the model for Totumas data? [[PR#241](https://github.com/AMI-system/antenna/pull/241)(MERGED)]
- 🔧 New model on Newfoundland species list (Current Quebec model is overestimating total number of species) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED)]
- 🔧 Species dataset made for image classification [[#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#741](https://github.com/AMI-system/antenna/pull/741)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#241](https://github.com/AMI-system/antenna/pull/241)(MERGED); [#628](https://github.com/AMI-system/antenna/issues/628)(CLOSED); [#621](https://github.com/AMI-system/antenna/issues/621)(CLOSED)]
- 🔧 Species of concern model (invasive & pest species) [[PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED)]
- 🔧 Missing Singapore classifier option [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#628](https://github.com/AMI-system/antenna/issues/628)(CLOSED); [#621](https://github.com/AMI-system/antenna/issues/621)(CLOSED); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 Partner-Specific Pipelines (e.g. dedicated forest pest pipeline) [[#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#1033](https://github.com/AMI-system/antenna/pull/1033)(MERGED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [PR#315](https://github.com/AMI-system/antenna/pull/315)(MERGED); [#766](https://github.com/AMI-system/antenna/issues/766)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#695](https://github.com/AMI-system/antenna/pull/695)(CLOSED); [#681](https://github.com/AMI-system/antenna/issues/681)(CLOSED); [PR#680](https://github.com/AMI-system/antenna/pull/680)(CLOSED); [#677](https://github.com/AMI-system/antenna/issues/677)(CLOSED)]

</details>

### Auth and Account Basics

_Fix password reset, sign-up flow, and basic role management so users can manage their own accounts._

**Effort:** L | **Items:** 11 | **Status:** 1 tracked in GitHub; 4 partially implemented; 6 untracked

**User stories:**
- As a user, I want to reset my password via email without needing developer assistance.
- As a project manager, I want to invite team members and assign roles so the right people have the right access.

<details>
<summary>Underlying items (11)</summary>

- 🔧 Reset password when not logged in (Backend configuration is incomplete maybe disable) (x5) [[#671](https://github.com/AMI-system/antenna/issues/671)(OPEN); [PR#526](https://github.com/AMI-system/antenna/pull/526)(MERGED)]
- 📋 Role Management UI (for Project Managers to invite members and assign roles) (x2) [[PR#727](https://github.com/AMI-system/antenna/pull/727)(CLOSED); [PR#1078](https://github.com/AMI-system/antenna/pull/1078)(CLOSED); [PR#1030](https://github.com/AMI-system/antenna/pull/1030)(OPEN)]
- ❌ Bug: Sign up as new user requires admin support (currently disabled) (x2)
- 🔧 Add Taxa model permissions to Identifier role [[PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#1035](https://github.com/AMI-system/antenna/pull/1035)(OPEN); [PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED)]
- ❌ Configure members for a project (Anna and Mohamed is currently working on this)
- 🔧 Create user interface for project managers to add new users and assign roles [[PR#1006](https://github.com/AMI-system/antenna/pull/1006)(OPEN); [PR#727](https://github.com/AMI-system/antenna/pull/727)(CLOSED); [PR#402](https://github.com/AMI-system/antenna/pull/402)(CLOSED); [PR#1030](https://github.com/AMI-system/antenna/pull/1030)(OPEN); [PR#233](https://github.com/AMI-system/antenna/pull/233)(CLOSED)]
- 🔧 Bug: Reset password when not logged in is unstable [[#671](https://github.com/AMI-system/antenna/issues/671)(OPEN); [PR#526](https://github.com/AMI-system/antenna/pull/526)(MERGED); [PR#525](https://github.com/AMI-system/antenna/pull/525)(MERGED)]
- ❌ Issue of shared credentials
- ❌ Sign up as new user on the platform
- ❌ User Account Management (re-enabling self-service sign-up)
- ❌ Role management (what about adding new users?)

</details>

### Honest Results at the Right Level

_Roll up to genus or family when the model is uncertain — coarser-but-confident predictions beat wrong species IDs._

**Effort:** L | **Items:** 10 | **Status:** 7 partially implemented; 3 untracked

**User stories:**
- As a taxonomist, I want the system to roll up to genus when it can't confidently identify to species, so results are honest rather than wrong.
- As a project manager, I want confidence-appropriate results in reports so partners trust the data.

<details>
<summary>Underlying items (10)</summary>

- ❌ How to roll up to genus, higher taxon levels
- 🔧 Roll up taxon ranks, Adapters, Temperature calibration [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 🔧 Confidence at higher ranks (Single determination approach & New column to show predictions) [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#712](https://github.com/AMI-system/antenna/pull/712)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED)]
- 🔧 Order-level classifier (refinement & calibration) and size estimation (x3) [[PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [PR#607](https://github.com/AMI-system/antenna/pull/607)(CLOSED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED)]
- 🔧 Integrate an Order-Level Classifier with the option to replace the current binary classifier [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#762](https://github.com/AMI-system/antenna/pull/762)(MERGED)]
- ❌ Display Top 3 labels with confidence score/uncertainty measures
- ❌ Display top N predictions
- 🔧 Downgrading predictions to higher taxonomic ranks until confidence is satisfactory. [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 🔧 Genus level prediction (? - evaluate the accuracy at genus level) [[PR#712](https://github.com/AMI-system/antenna/pull/712)(MERGED); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)]
- 🔧 Order level classifier (Aditya's work) [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#762](https://github.com/AMI-system/antenna/pull/762)(MERGED)]

</details>

### Confidence You Can Measure

_Estimate and display how confident the system is about each prediction using accuracy metrics per species, region, and camera._

**Effort:** L | **Items:** 10 | **Status:** 4 tracked in GitHub; 5 partially implemented; 1 untracked

**User stories:**
- As a field ecologist, I want to see how accurate the model is on my specific data so I know when to trust it.
- As a project manager, I want auto-generated accuracy reports so I can include reliability statements in publications.
- As an ML researcher, I want per-class confidence calibration so I can identify where the model needs improvement.

<details>
<summary>Underlying items (10)</summary>

- ❌ Confidence & Uncertainty in UI (displaying species-level accuracy)
- 📋 Calibration (What species can we be confident about) [[PR#788](https://github.com/AMI-system/antenna/pull/788)(OPEN); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED)]
- 🔧 More informative confidence scores (calibrated scores) (x2) [[PR#607](https://github.com/AMI-system/antenna/pull/607)(CLOSED); [#357](https://github.com/AMI-system/antenna/issues/357)(CLOSED); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED)]
- 🔧 Work on new uncertainty measurements [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 📋 Estimating confidence how to present low-confidence results to users [[PR#386](https://github.com/AMI-system/antenna/pull/386)(OPEN); [#357](https://github.com/AMI-system/antenna/issues/357)(CLOSED); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED)]
- 🔧 Transparency: Knowing what we don't know - which species good and bad at [[PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#811](https://github.com/AMI-system/antenna/issues/811)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED)]
- 📋 Determine our certainty / uncertainty at predicting that species [[PR#386](https://github.com/AMI-system/antenna/pull/386)(OPEN); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED)]
- 🔧 How to score confidence (hardness to identify visually, how many similar species, the models accuracy on this species, the number and quality of training samples (or type of images) for this species). Do we know about it at all? How likely is the species to occur at the place and time it was observed? [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 🔧 Research focus on uncertainty metrics and UI/UX features for predictions [[PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)]
- 📋 Test sets for standard evaluation of models [[PR#816](https://github.com/AMI-system/antenna/pull/816)(OPEN)]

</details>

### Remove Bad Data Automatically

_Filter out blurry, cut-off, or too-small detections before classification so results aren't polluted by junk._

**Effort:** L | **Items:** 10 | **Status:** 1 tracked in GitHub; 9 partially implemented

**User stories:**
- As a field ecologist, I want the system to skip images that are too blurry or partial so I only review real observations.
- As a project manager, I want cleaner results by default so species counts reflect actual biodiversity, not image artifacts.

<details>
<summary>Underlying items (10)</summary>

- 🔧 Automated Quality Filters (to auto-remove blurry/dark/tiny images) (x2) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED)]
- 🔧 Post processing functions (small, blurry, tracking sequential detections) / Reducing noise (x2) [[PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [PR#484](https://github.com/AMI-system/antenna/pull/484)(OPEN); [#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED)]
- 🔧 Post processing functions – special sauce (small/blurry/tracking) (x2) [[#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#863](https://github.com/AMI-system/antenna/issues/863)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN)]
- 🔧 Post-Processing Functions (Class Masking/small/blurry/darkness filter) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#706](https://github.com/AMI-system/antenna/pull/706)(CLOSED)]
- 🔧 Embarrassing things (IDing smudges with high confidence single subject images) [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#389](https://github.com/AMI-system/antenna/pull/389)(MERGED)]
- 🔧 See results that are accurate enough (Improve filtering, post-processing, pre-configurations) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#1022](https://github.com/AMI-system/antenna/pull/1022)(MERGED)]
- 🔧 Post processing framework and UI [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED); [#1110](https://github.com/AMI-system/antenna/issues/1110)(OPEN); [#1052](https://github.com/AMI-system/antenna/issues/1052)(OPEN); [#1010](https://github.com/AMI-system/antenna/issues/1010)(OPEN); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#693](https://github.com/AMI-system/antenna/pull/693)(MERGED)]
- 🔧 Post-processing based on image quality (what are we unconfident about) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED)]
- 📋 Improving/Reducing noise in results displayed by default [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN)]
- 🔧 Implement enhanced post-processing techniques (moths & insects specific) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN)]

</details>

### Filter Results to Your Region

_Restrict predictions to plausible species using regional checklists, geofencing, and class masking._

**Effort:** M | **Items:** 8 | **Status:** 2 tracked in GitHub; 6 partially implemented

**User stories:**
- As a field ecologist, I want predictions restricted to species in my region so I don't waste time on impossible IDs.
- As a project manager, I want geofenced results so partner reports only include locally plausible species.

<details>
<summary>Underlying items (8)</summary>

- 📋 Restrict to species list (Class masking) (x4) [[#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN)]
- 📋 Class masking of one of the existing models [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 Class masking to regional species checklists [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 Default pipelines by project/location [[PR#979](https://github.com/AMI-system/antenna/pull/979)(MERGED); [PR#949](https://github.com/AMI-system/antenna/pull/949)(MERGED); [PR#784](https://github.com/AMI-system/antenna/pull/784)(MERGED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [PR#705](https://github.com/AMI-system/antenna/pull/705)(MERGED); [PR#684](https://github.com/AMI-system/antenna/pull/684)(MERGED); [PR#479](https://github.com/AMI-system/antenna/pull/479)(MERGED); [PR#315](https://github.com/AMI-system/antenna/pull/315)(MERGED); [#982](https://github.com/AMI-system/antenna/issues/982)(OPEN); [PR#936](https://github.com/AMI-system/antenna/pull/936)(OPEN)]
- 🔧 Feature for masking predictions to a species list (as an alternative to a regional model) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 Geofencing using species list for improving results [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED)]
- 🔧 Transparency: This region is not supported [[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 How to incorporate geopriors exactly? Part of model, or post-filtering. [[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]

</details>

### Improved Insect Detector

_Reduce duplicate detections, handle more camera types, and skip non-insect artifacts in high-volume scenarios._

**Effort:** M | **Items:** 8 | **Status:** 2 tracked in GitHub; 6 partially implemented

**User stories:**
- As a field ecologist, I want fewer false detections so I spend less time dismissing non-insects.
- As an ML researcher, I want the detector to handle overlapping detections better so downstream classification isn't confused.

<details>
<summary>Underlying items (8)</summary>

- 🔧 Better Detector/Segmenter (segmentation detector/handling overlapping moths) (x2) [[#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)]
- 📋 Make detection box directly clickable [[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN)]
- 📋 Make all detections visible [[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN)]
- 🔧 Detector with segmentation (for biomass estimation) [[#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#656](https://github.com/AMI-system/antenna/pull/656)(MERGED)]
- 🔧 Segmentation detector (e.g., HQ Sam, GroundingSAM, Depth Anything, Flatbug, OWLv2) [[#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)]
- 🔧 Handle overlapping moths [[PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#459](https://github.com/AMI-system/antenna/pull/459)(MERGED)]
- 🔧 Discuss detector approaches [[PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#656](https://github.com/AMI-system/antenna/pull/656)(MERGED); [PR#596](https://github.com/AMI-system/antenna/pull/596)(MERGED); [PR#285](https://github.com/AMI-system/antenna/pull/285)(MERGED); [PR#183](https://github.com/AMI-system/antenna/pull/183)(MERGED); [PR#115](https://github.com/AMI-system/antenna/pull/115)(MERGED); [PR#1059](https://github.com/AMI-system/antenna/pull/1059)(OPEN); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED)]
- 🔧 Object detector only works... (implied limitation) [[#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#183](https://github.com/AMI-system/antenna/pull/183)(MERGED); [PR#115](https://github.com/AMI-system/antenna/pull/115)(MERGED); [#1092](https://github.com/AMI-system/antenna/issues/1092)(OPEN); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED)]

</details>

### Track Insects Across Frames

_Use multiple detections of the same individual across frames to improve species identification of occurrences._

**Effort:** M | **Items:** 5 | **Status:** 1 tracked in GitHub; 4 partially implemented

**User stories:**
- As a field ecologist, I want the system to combine evidence from multiple photos of the same insect to get a more reliable ID.
- As an ML researcher, I want temporal tracking to aggregate classification scores across detections for better occurrence-level predictions.

<details>
<summary>Underlying items (5)</summary>

- 📋 Tracking (x2) [[#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#863](https://github.com/AMI-system/antenna/issues/863)(OPEN); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN); [PR#484](https://github.com/AMI-system/antenna/pull/484)(OPEN); [#264](https://github.com/AMI-system/antenna/issues/264)(CLOSED)]
- 🔧 Integrate Tracking and Feature Vectors to improve prediction results [[PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN); [#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [#863](https://github.com/AMI-system/antenna/issues/863)(OPEN); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#670](https://github.com/AMI-system/antenna/pull/670)(MERGED)]
- 🔧 Tracking for counting (biomass estimation) [[#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#863](https://github.com/AMI-system/antenna/issues/863)(OPEN); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN); [PR#484](https://github.com/AMI-system/antenna/pull/484)(OPEN); [#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [#264](https://github.com/AMI-system/antenna/issues/264)(CLOSED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED)]
- 🔧 Beyond Species ID: biomass estimation/pixel-to-size calibration/tracking [[PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED)]
- 🔧 How to choose ID from a track / turboid of multiple images [[#1121](https://github.com/AMI-system/antenna/issues/1121)(OPEN); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#863](https://github.com/AMI-system/antenna/issues/863)(OPEN); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN); [PR#484](https://github.com/AMI-system/antenna/pull/484)(OPEN); [#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [#264](https://github.com/AMI-system/antenna/issues/264)(CLOSED); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED)]

</details>

### Better Default Settings

_Ship sensible defaults that hide noise — confidence thresholds, non-insect class hiding, and per-project configuration._

**Effort:** S | **Items:** 3 | **Status:** 1 tracked in GitHub; 1 partially implemented; 1 untracked

**User stories:**
- As a new user, I want the system to show useful results out of the box without needing to configure thresholds manually.
- As a project manager, I want project-level default filters so my team sees clean results without individual setup.

<details>
<summary>Underlying items (3)</summary>

- 🔧 Improve presented prediction results (Filtering, good defaults, post-processing) [[PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED)]
- ❌ Good defaults & presets - hiding noise lower quality results
- 📋 Hide occurrences if missing detections [[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN)]

</details>

### New Processing Pipeline

_Get the new async processing pipeline running and tested with partner data for real-world feedback._

**Effort:** S | **Items:** 3 | **Status:** 1 tracked in GitHub; 2 partially implemented

**User stories:**
- As a project manager, I want reliable automated processing so results arrive without manual intervention.
- As an ML researcher, I want to test new models on partner data to validate improvements before wider rollout.

<details>
<summary>Underlying items (3)</summary>

- 🔧 Processing stability / Processing v2 [[#1112](https://github.com/AMI-system/antenna/issues/1112)(OPEN); [PR#1125](https://github.com/AMI-system/antenna/pull/1125)(MERGED); [PR#1113](https://github.com/AMI-system/antenna/pull/1113)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#1111](https://github.com/AMI-system/antenna/issues/1111)(OPEN); [#1085](https://github.com/AMI-system/antenna/issues/1085)(OPEN); [#1084](https://github.com/AMI-system/antenna/issues/1084)(CLOSED); [#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [#910](https://github.com/AMI-system/antenna/issues/910)(OPEN)]
- 📋 Implement more algorithms and a better worker system [[#515](https://github.com/AMI-system/antenna/issues/515)(OPEN); [#910](https://github.com/AMI-system/antenna/issues/910)(OPEN); [#802](https://github.com/AMI-system/antenna/issues/802)(CLOSED); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [#912](https://github.com/AMI-system/antenna/issues/912)(OPEN); [#695](https://github.com/AMI-system/antenna/issues/695)(CLOSED); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [#1011](https://github.com/AMI-system/antenna/issues/1011)(OPEN); [PR#1109](https://github.com/AMI-system/antenna/pull/1109)(MERGED); [PR#949](https://github.com/AMI-system/antenna/pull/949)(MERGED)]
- 🔧 Experiment with multiple models (order-level classifier object detection/clustering) [[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)]

</details>

### Verification That Scales

_Suggest which occurrences to verify for maximum calibration value instead of verifying everything one by one._

**Effort:** S | **Items:** 2 | **Status:** 1 tracked in GitHub; 1 untracked

**User stories:**
- As a taxonomist, I want the system to suggest which identifications need my attention most so I use my time efficiently.
- As a field ecologist, I want to know when I've verified enough to trust the overall results so I can stop checking every record.
- As an ML researcher, I want to identify which verified records would be most valuable for model retraining.

<details>
<summary>Underlying items (2)</summary>

- 📋 Filtering by what has been vetted [[#1032](https://github.com/AMI-system/antenna/issues/1032)(OPEN); [PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [#615](https://github.com/AMI-system/antenna/issues/615)(CLOSED)]
- ❌ Tracking Progress: Knowing what's been processed/verified (x2)

</details>

### Processing Reliability

_Make jobs complete consistently — fix timeouts, improve error handling, and add progress visibility._

**Effort:** S | **Items:** 2 | **Status:** 2 partially implemented

**User stories:**
- As a project manager, I want to see real-time progress of processing jobs so I know what's happening.
- As a field ecologist, I want failed jobs to recover gracefully instead of losing all progress.

<details>
<summary>Underlying items (2)</summary>

- 🔧 Processing stability/stabilization (x3) [[#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [#1072](https://github.com/AMI-system/antenna/issues/1072)(CLOSED); [#782](https://github.com/AMI-system/antenna/issues/782)(CLOSED); [PR#934](https://github.com/AMI-system/antenna/pull/934)(MERGED); [#1117](https://github.com/AMI-system/antenna/issues/1117)(OPEN); [PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#554](https://github.com/AMI-system/antenna/pull/554)(MERGED); [#633](https://github.com/AMI-system/antenna/issues/633)(CLOSED); [#1025](https://github.com/AMI-system/antenna/issues/1025)(OPEN)]
- 🔧 Still some sessions with unprocessed images [[PR#691](https://github.com/AMI-system/antenna/pull/691)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [PR#718](https://github.com/AMI-system/antenna/pull/718)(CLOSED); [PR#585](https://github.com/AMI-system/antenna/pull/585)(CLOSED)]

</details>

## Maybe (Next 6 Months) — 12 cards, 335 items

_Strong candidates to move into 'Now' as capacity frees up or partner needs emerge._

### UI Polish and Consistency

_Fix layout issues, improve date pickers, make responsive design work, and standardize component patterns._

**Effort:** XL | **Items:** 77 | **Status:** 5 partially implemented; 72 untracked

**User stories:**
- As any user, I want the interface to be consistent and predictable so I can learn it once and navigate confidently.
- As a field ecologist working on a tablet, I want the UI to work well on smaller screens.

<details>
<summary>Underlying items (77)</summary>

- ❌ Project ID required when changing name/tags of cluster
- 🔧 Hide occurrences if missing detections [[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#596](https://github.com/AMI-system/antenna/pull/596)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [#706](https://github.com/AMI-system/antenna/issues/706)(CLOSED); [#618](https://github.com/AMI-system/antenna/issues/618)(CLOSED); [#473](https://github.com/AMI-system/antenna/issues/473)(OPEN); [PR#181](https://github.com/AMI-system/antenna/pull/181)(MERGED); [#985](https://github.com/AMI-system/antenna/issues/985)(CLOSED); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED)]
- 🔧 Use Google spreadsheets for collaborative updates to species lists and training data [[PR#717](https://github.com/AMI-system/antenna/pull/717)(MERGED); [#601](https://github.com/AMI-system/antenna/issues/601)(OPEN); [#770](https://github.com/AMI-system/antenna/issues/770)(CLOSED); [#907](https://github.com/AMI-system/antenna/issues/907)(OPEN); [PR#184](https://github.com/AMI-system/antenna/pull/184)(MERGED); [PR#661](https://github.com/AMI-system/antenna/pull/661)(MERGED); [#755](https://github.com/AMI-system/antenna/issues/755)(OPEN); [#864](https://github.com/AMI-system/antenna/issues/864)(CLOSED); [PR#626](https://github.com/AMI-system/antenna/pull/626)(MERGED); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED)]
- 🔧 Suggests classification of derived data: Detections -> Occurrences -> Species [[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#596](https://github.com/AMI-system/antenna/pull/596)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [#706](https://github.com/AMI-system/antenna/issues/706)(CLOSED); [#618](https://github.com/AMI-system/antenna/issues/618)(CLOSED); [#473](https://github.com/AMI-system/antenna/issues/473)(OPEN); [PR#181](https://github.com/AMI-system/antenna/pull/181)(MERGED); [#985](https://github.com/AMI-system/antenna/issues/985)(CLOSED); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED)]
- 🔧 Tags for occurrences [[PR#608](https://github.com/AMI-system/antenna/pull/608)(MERGED); [#682](https://github.com/AMI-system/antenna/issues/682)(CLOSED); [PR#861](https://github.com/AMI-system/antenna/pull/861)(MERGED); [#865](https://github.com/AMI-system/antenna/issues/865)(OPEN); [#570](https://github.com/AMI-system/antenna/issues/570)(OPEN); [#991](https://github.com/AMI-system/antenna/issues/991)(CLOSED); [#541](https://github.com/AMI-system/antenna/issues/541)(CLOSED); [PR#1038](https://github.com/AMI-system/antenna/pull/1038)(MERGED); [PR#359](https://github.com/AMI-system/antenna/pull/359)(MERGED); [#298](https://github.com/AMI-system/antenna/issues/298)(OPEN)]
- ❌ Missing images
- ❌ Data management issues (rotated images/missing metadata/bad data)
- ❌ Remove "null" that keeps returning to data sync view (x2)
- ❌ More inline help for users
- ❌ New home for Antenna docs!
- ❌ Documentation & doc links within app
- 🔧 Streamline form handling across app [[#254](https://github.com/AMI-system/antenna/issues/254)(CLOSED); [PR#74](https://github.com/AMI-system/antenna/pull/74)(MERGED); [#1106](https://github.com/AMI-system/antenna/issues/1106)(OPEN); [#317](https://github.com/AMI-system/antenna/issues/317)(OPEN); [PR#929](https://github.com/AMI-system/antenna/pull/929)(MERGED); [PR#448](https://github.com/AMI-system/antenna/pull/448)(MERGED); [#336](https://github.com/AMI-system/antenna/issues/336)(CLOSED); [#260](https://github.com/AMI-system/antenna/issues/260)(OPEN); [#834](https://github.com/AMI-system/antenna/issues/834)(OPEN)]
- ❌ Streamline form handling across app
- ❌ Complete migration of UI components from raw Radix primitives to shadcn/ui
- ❌ Complete migration from style modules to Tailwind CSS
- ❌ Add multilingual localization support
- ❌ Continuing to make tickets in ami-admin repo and track ongoing projects
- ❌ Ability to demo models & techniques more easily (without setting up a research project) - Focus on internal use
- ❌ Merge PRs - project ID filter
- ❌ Automating the current interface (prototype)
- ❌ Switch to a JS framework in 2026
- ❌ Split up backend modules
- ❌ Complete migration of UI components from raw Radix primitives to shadcn/ui
- ❌ Complete migration from style modules to Tailwind CSS
- ❌ Move UI kit back to Antenna repo
- ❌ Migrate to React 19
- ❌ Migrate to Next.js (simplify routing and code splitting)
- ❌ Represent Antenna UI in Figma (for high fidelity prototyping)
- ❌ Upgrade Node.js
- ❌ ML Developer & researcher experience for improving ML
- ❌ Implement date filtering
- ❌ Display projects user is part of/manager of in My Antenna
- ❌ Display user's focused species in My Antenna
- ❌ Not identifiable based on current image quick action
- ❌ Never identifiable based on image quick action
- ❌ I personally can not ID this quick action
- ❌ Incorrect (based on my knowledge) quick reaction
- ❌ Family/genus/tribe correct quick reaction
- ❌ Provide a list of species to choose from for validation/annotation
- ❌ Provide a mechanism for regional experts to flag instances for further investigation
- ❌ Quick flagging
- ❌ Show Num Captures column under deployments.
- ❌ Represent Antenna UI in Figma (for high fidelity prototyping)
- ❌ Don't show Not a Moth by default (need project setting for these special Taxon)
- ❌ Bug: Cluster cover images are not automatically set
- ❌ Should always be encouraging and pleasurable to use.
- ❌ Clear distinction for "3rd party" vs. certified models (Antenna logo!)
- ❌ Citizen science page with a downloadable button
- ❌ Clarify indication for unprocessed collections
- ❌ Connect comments box
- ❌ Clarify saving changes (automatic vs. manual)
- ❌ Back button should retain selected filters
- ❌ Make filters more visible for intuitive understanding
- ❌ Make thumbnails clickable
- ❌ Auto-refresh image after single image job completion
- ❌ Continue to maintain the ability to see detailed information about captured images
- ❌ Continue to maintain the clean interface of the software
- ❌ Continue to maintain the intuitive navigation and user-friendly interface
- ❌ Make some interface elements like the filter bar fixed
- ❌ Expose deployment drop-down when registering a new job
- ❌ Auto-open status modal when single job is started
- ❌ Discussion Collections terminology
- ❌ More prototypes
- ❌ Getting user personas and user stories on paper
- ❌ Need tooltips? Walkthrough dialogs?
- ❌ Filters vs project settings
- ❌ Idea on how to disable filters
- ❌ Ability to delete a site/pipeline/or device type
- ❌ Search project option on the main page
- ❌ Register new project button hard to find
- ❌ Transition Sign-Up buttons to Contact Us (Strategic)
- ❌ Software incorrectly ID'd moss/bark as moth species with no way to report
- ❌ Pipeline tag isn't really clear
- ❌ Image illustrating projects should be scaled to the size of rectangular window
- ❌ Regex null bug (UI gap)
- ❌ Regex null bug
- ❌ Transition "Sign-Up" buttons to "Contact Us"

</details>

### User Guide and Tutorials

_Step-by-step documentation for common workflows: project setup, reviewing results, exporting data._

**Effort:** XL | **Items:** 48 | **Status:** 1 tracked in GitHub; 47 untracked

**User stories:**
- As a field ecologist, I want a guide that walks me through setting up a new monitoring project from start to finish.
- As a new user, I want tutorial videos or walkthroughs so I can learn the platform without live training.

<details>
<summary>Underlying items (48)</summary>

- ❌ Configure pipelines for a project (Needs documentation) (x3)
- ❌ Documentation of how to re-train a model with data from Antenna (x3)
- ❌ Needs documentation for configuring processing services, pipelines, storage, and data source (x3)
- ❌ Research & document plan for easier data import from cameras/SD cards (x3)
- ❌ Documentation for reviewing (x2)
- ❌ Link to documentation (and write documentation!) / Documentation Sprint (x2)
- ❌ Use LLM to help with the table of contents for documentation (x2)
- ❌ Documentation - for users (user guide) and developers (x2)
- ❌ Configure processing services for a project (Needs documentation) (x2)
- ❌ Clarify/flesh out what processing means when a collection is launched
- ❌ Provide more guidance/documentation on collections (definition purpose how to use strategy)
- ❌ Prioritize documentation for the verification process
- ❌ Create logic diagrams for new & existing features
- ❌ Add megadector-> butterflies example.
- ❌ Complete documentation & improving self-service
- ❌ Antenna workflow/requirements
- ❌ One good case study.
- ❌ Exporting data & updating the offline guide
- 📋 Configure a data source for a station [[#1047](https://github.com/AMI-system/antenna/issues/1047)(OPEN)]
- ❌ Setup a collection of captures
- ❌ Requirements doc - Mapping the pipeline - Documentation for internal use - Showing where the gaps are in the steps
- ❌ Documentation - first for internal then for public
- ❌ Training support team documentation/videos (Public/Private Wiki, User Manual)
- ❌ Clarify that collections are fixed queries until recalculation
- ❌ Clarify confirmation of moth presence over multiple days
- ❌ Clarify confusion about data flow and image processing integration
- ❌ Emphasize importance of proving data origin
- ❌ Assumption of manual entry for first & last date
- ❌ Clarify device and deployment hierarchies with diagrams or text explanations
- ❌ Create Wiki manual with specific process notes
- ❌ Confusion about implications of renaming folders and files within the object store
- ❌ Suggest avoiding spaces in folder names for better compatibility
- ❌ Provide instructions for uploading large batches of images using Cyberduck
- ❌ At least one documentation ticket
- ❌ Configure processing services/pipelines
- ❌ Configure a storage/data source
- ❌ Demonstration for self-installation
- ❌ RUNNING ANTENNA LOCALLY
- ❌ Make an instructions file about the frontend overall
- ❌ Configure a data source for a station (Needs documentation)
- ❌ Register existing projects and process 2 years of data (Next 6 months)
- ❌ Full support for current research projects before self-service for public
- ❌ Self-service ready? (Out of BETA officially)
- ❌ Difficulty with command-line interfaces and IT restrictions
- ❌ Document full vision of complete AMI solution at scale
- ❌ Michael to assist with technical description of methods for new paper
- ❌ Updated diagrams for presentations in October
- ❌ Mind map of what's to come after this

</details>

### Infrastructure and DevOps

_Improve CI/CD, monitoring, logging, and deployment automation for reliability and developer productivity._

**Effort:** XL | **Items:** 47 | **Status:** 26 partially implemented; 21 untracked

**User stories:**
- As a developer, I want reliable CI/CD so I can deploy with confidence.
- As an admin, I want monitoring dashboards so I can detect issues before users report them.

<details>
<summary>Underlying items (47)</summary>

- 🔧 Optimization features & "hardening" (including Image resizing) (x3) [[#236](https://github.com/AMI-system/antenna/issues/236)(OPEN); [PR#348](https://github.com/AMI-system/antenna/pull/348)(MERGED); [#419](https://github.com/AMI-system/antenna/issues/419)(OPEN); [#729](https://github.com/AMI-system/antenna/issues/729)(OPEN)]
- 🔧 Bug: Increase capacity of the database in the OOD environment (x2) [[PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#410](https://github.com/AMI-system/antenna/issues/410)(CLOSED)]
- 🔧 DB Table partitions (Partitioning/Database Scaling/Optimization) (x2) [[PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [#607](https://github.com/AMI-system/antenna/issues/607)(CLOSED); [PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED)]
- 🔧 Background job system logging per job [[PR#303](https://github.com/AMI-system/antenna/pull/303)(MERGED); [#404](https://github.com/AMI-system/antenna/issues/404)(CLOSED); [PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [PR#268](https://github.com/AMI-system/antenna/pull/268)(MERGED); [PR#919](https://github.com/AMI-system/antenna/pull/919)(MERGED); [#922](https://github.com/AMI-system/antenna/issues/922)(OPEN); [PR#368](https://github.com/AMI-system/antenna/pull/368)(MERGED); [#633](https://github.com/AMI-system/antenna/issues/633)(CLOSED); [#1117](https://github.com/AMI-system/antenna/issues/1117)(OPEN)]
- 🔧 Run an XL ML job (VISS project) [[PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [#922](https://github.com/AMI-system/antenna/issues/922)(OPEN); [PR#303](https://github.com/AMI-system/antenna/pull/303)(MERGED); [#404](https://github.com/AMI-system/antenna/issues/404)(CLOSED); [#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [PR#268](https://github.com/AMI-system/antenna/pull/268)(MERGED); [PR#919](https://github.com/AMI-system/antenna/pull/919)(MERGED); [PR#368](https://github.com/AMI-system/antenna/pull/368)(MERGED); [#1117](https://github.com/AMI-system/antenna/issues/1117)(OPEN); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED)]
- 🔧 Time for refactoring (switching to Next.js) [[PR#179](https://github.com/AMI-system/antenna/pull/179)(MERGED); [#1010](https://github.com/AMI-system/antenna/issues/1010)(OPEN); [#723](https://github.com/AMI-system/antenna/issues/723)(CLOSED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [PR#704](https://github.com/AMI-system/antenna/pull/704)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [#398](https://github.com/AMI-system/antenna/issues/398)(OPEN)]
- 🔧 Migrate to React 19 [[#1010](https://github.com/AMI-system/antenna/issues/1010)(OPEN); [#999](https://github.com/AMI-system/antenna/issues/999)(OPEN); [PR#179](https://github.com/AMI-system/antenna/pull/179)(MERGED)]
- 🔧 Migrate to Next.js (to simplify routing and code splitting) [[#1010](https://github.com/AMI-system/antenna/issues/1010)(OPEN); [#999](https://github.com/AMI-system/antenna/issues/999)(OPEN); [PR#179](https://github.com/AMI-system/antenna/pull/179)(MERGED)]
- 🔧 Multiple environments and auto deployment (Dev, Staging, Branch deploys, Demo, Production) [[#648](https://github.com/AMI-system/antenna/issues/648)(OPEN); [PR#492](https://github.com/AMI-system/antenna/pull/492)(MERGED); [PR#422](https://github.com/AMI-system/antenna/pull/422)(MERGED); [PR#152](https://github.com/AMI-system/antenna/pull/152)(MERGED); [#344](https://github.com/AMI-system/antenna/issues/344)(CLOSED); [PR#367](https://github.com/AMI-system/antenna/pull/367)(MERGED); [PR#353](https://github.com/AMI-system/antenna/pull/353)(MERGED); [PR#230](https://github.com/AMI-system/antenna/pull/230)(MERGED); [#1088](https://github.com/AMI-system/antenna/issues/1088)(OPEN); [#714](https://github.com/AMI-system/antenna/issues/714)(OPEN)]
- 🔧 Focus on portability, quick install, cloud & local [[#1069](https://github.com/AMI-system/antenna/issues/1069)(CLOSED); [PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#554](https://github.com/AMI-system/antenna/pull/554)(MERGED); [#1072](https://github.com/AMI-system/antenna/issues/1072)(CLOSED); [#782](https://github.com/AMI-system/antenna/issues/782)(CLOSED); [#633](https://github.com/AMI-system/antenna/issues/633)(CLOSED); [#370](https://github.com/AMI-system/antenna/issues/370)(CLOSED); [#1117](https://github.com/AMI-system/antenna/issues/1117)(OPEN); [#1025](https://github.com/AMI-system/antenna/issues/1025)(OPEN)]
- 🔧 Improving image quality of cameras [[#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [PR#353](https://github.com/AMI-system/antenna/pull/353)(MERGED); [#344](https://github.com/AMI-system/antenna/issues/344)(CLOSED); [#207](https://github.com/AMI-system/antenna/issues/207)(CLOSED); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED); [PR#1002](https://github.com/AMI-system/antenna/pull/1002)(MERGED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#492](https://github.com/AMI-system/antenna/pull/492)(MERGED); [PR#422](https://github.com/AMI-system/antenna/pull/422)(MERGED); [PR#367](https://github.com/AMI-system/antenna/pull/367)(MERGED)]
- 🔧 Script to fix date offsets [[PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#704](https://github.com/AMI-system/antenna/pull/704)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [#398](https://github.com/AMI-system/antenna/issues/398)(OPEN); [#723](https://github.com/AMI-system/antenna/issues/723)(CLOSED); [#1124](https://github.com/AMI-system/antenna/issues/1124)(OPEN); [PR#854](https://github.com/AMI-system/antenna/pull/854)(MERGED)]
- 🔧 Registration of pipelines (Self-service feature remaining) [[#912](https://github.com/AMI-system/antenna/issues/912)(OPEN); [#1011](https://github.com/AMI-system/antenna/issues/1011)(OPEN); [#695](https://github.com/AMI-system/antenna/issues/695)(CLOSED); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [PR#949](https://github.com/AMI-system/antenna/pull/949)(MERGED); [PR#784](https://github.com/AMI-system/antenna/pull/784)(MERGED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [PR#722](https://github.com/AMI-system/antenna/pull/722)(MERGED); [PR#576](https://github.com/AMI-system/antenna/pull/576)(MERGED); [#539](https://github.com/AMI-system/antenna/issues/539)(OPEN)]
- 🔧 Model Registry & Available Pipelines (Registry for models & ML backends) [[#532](https://github.com/AMI-system/antenna/issues/532)(OPEN); [#912](https://github.com/AMI-system/antenna/issues/912)(OPEN); [#695](https://github.com/AMI-system/antenna/issues/695)(CLOSED); [PR#738](https://github.com/AMI-system/antenna/pull/738)(MERGED); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [#1011](https://github.com/AMI-system/antenna/issues/1011)(OPEN); [PR#949](https://github.com/AMI-system/antenna/pull/949)(MERGED); [PR#784](https://github.com/AMI-system/antenna/pull/784)(MERGED); [PR#722](https://github.com/AMI-system/antenna/pull/722)(MERGED); [PR#576](https://github.com/AMI-system/antenna/pull/576)(MERGED)]
- 🔧 Speed/Performance (Top priority, scaling up processing) [[#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#410](https://github.com/AMI-system/antenna/issues/410)(CLOSED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED)]
- 🔧 Stable production environment with automated backups & good performance [[#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [#685](https://github.com/AMI-system/antenna/issues/685)(CLOSED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [#410](https://github.com/AMI-system/antenna/issues/410)(CLOSED)]
- 🔧 Scaling up infrastructure (robustness) [[PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED); [PR#422](https://github.com/AMI-system/antenna/pull/422)(MERGED)]
- 🔧 Setup vector database [[#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [#607](https://github.com/AMI-system/antenna/issues/607)(CLOSED); [PR#228](https://github.com/AMI-system/antenna/pull/228)(MERGED)]
- 🔧 Work on integration structure of models and training data [[PR#202](https://github.com/AMI-system/antenna/pull/202)(MERGED); [#1089](https://github.com/AMI-system/antenna/issues/1089)(OPEN); [#226](https://github.com/AMI-system/antenna/issues/226)(CLOSED); [PR#112](https://github.com/AMI-system/antenna/pull/112)(MERGED); [PR#111](https://github.com/AMI-system/antenna/pull/111)(MERGED); [PR#921](https://github.com/AMI-system/antenna/pull/921)(MERGED); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED); [PR#647](https://github.com/AMI-system/antenna/pull/647)(MERGED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED); [#667](https://github.com/AMI-system/antenna/issues/667)(CLOSED)]
- ❌ Fix initial difficulty with configuring Amazon S3 settings
- 🔧 Enable remote data transfer from isolated northern deployments [[#307](https://github.com/AMI-system/antenna/issues/307)(OPEN); [#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#439](https://github.com/AMI-system/antenna/issues/439)(OPEN); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED); [#611](https://github.com/AMI-system/antenna/issues/611)(OPEN); [#258](https://github.com/AMI-system/antenna/issues/258)(OPEN); [PR#367](https://github.com/AMI-system/antenna/pull/367)(MERGED); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN)]
- ❌ Fix slower image loading
- ❌ Fix very slow image loading
- 🔧 Increase image resolution threshold to accommodate high-resolution images [[PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [PR#704](https://github.com/AMI-system/antenna/pull/704)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [#398](https://github.com/AMI-system/antenna/issues/398)(OPEN); [#723](https://github.com/AMI-system/antenna/issues/723)(CLOSED); [#1124](https://github.com/AMI-system/antenna/issues/1124)(OPEN); [PR#854](https://github.com/AMI-system/antenna/pull/854)(MERGED)]
- 🔧 Note on slow overall internet affecting performance [[#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#410](https://github.com/AMI-system/antenna/issues/410)(CLOSED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED)]
- ❌ Stability issues on the platform
- 🔧 DB partitioning exploration and implementation [[#900](https://github.com/AMI-system/antenna/issues/900)(CLOSED); [PR#380](https://github.com/AMI-system/antenna/pull/380)(MERGED); [#776](https://github.com/AMI-system/antenna/issues/776)(CLOSED); [#1097](https://github.com/AMI-system/antenna/issues/1097)(OPEN); [PR#860](https://github.com/AMI-system/antenna/pull/860)(MERGED); [PR#506](https://github.com/AMI-system/antenna/pull/506)(MERGED); [#411](https://github.com/AMI-system/antenna/issues/411)(CLOSED); [#239](https://github.com/AMI-system/antenna/issues/239)(CLOSED); [PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED); [PR#422](https://github.com/AMI-system/antenna/pull/422)(MERGED)]
- 🔧 Support for web-connected devices (continuous upload & processing) [[#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [#904](https://github.com/AMI-system/antenna/issues/904)(OPEN); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#977](https://github.com/AMI-system/antenna/issues/977)(OPEN); [PR#898](https://github.com/AMI-system/antenna/pull/898)(MERGED); [#958](https://github.com/AMI-system/antenna/issues/958)(OPEN); [#611](https://github.com/AMI-system/antenna/issues/611)(OPEN); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED)]
- 🔧 IMAGE THUMBNAILING - Faster scrubbing (mp4s) [[#236](https://github.com/AMI-system/antenna/issues/236)(OPEN); [PR#348](https://github.com/AMI-system/antenna/pull/348)(MERGED); [#419](https://github.com/AMI-system/antenna/issues/419)(OPEN); [#729](https://github.com/AMI-system/antenna/issues/729)(OPEN)]
- 🔧 Switch from form data to application/json [[PR#146](https://github.com/AMI-system/antenna/pull/146)(MERGED); [PR#688](https://github.com/AMI-system/antenna/pull/688)(MERGED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [#543](https://github.com/AMI-system/antenna/issues/543)(OPEN); [PR#448](https://github.com/AMI-system/antenna/pull/448)(MERGED); [PR#266](https://github.com/AMI-system/antenna/pull/266)(MERGED); [PR#231](https://github.com/AMI-system/antenna/pull/231)(MERGED); [#593](https://github.com/AMI-system/antenna/issues/593)(OPEN)]
- ❌ Implement Optimizations for speed (MVP feature)
- ❌ Use modularity to help divide ownership
- ❌ Ensure platform interoperability trap agnostic and modular design
- ❌ Use JASMIN for storage
- ❌ Help with processing of samples (since the feature is not stable enough yet)
- ❌ Focus on hardening (stability fixes speed) Processing fixing gaps in workflow
- ❌ Upgrade Node.js?
- ❌ Split up backend modules
- ❌ Everything related to the infrastructure (accounted for)
- ❌ Processing speed & stability (switch to producer/consumer model)
- ❌ Capturing data (sending direct to antenna)
- ❌ Support for per-bucket permissions for S3/Swift keys
- ❌ Allow more CEPHFS shares
- ❌ Switch background tasks from long running to many short
- ❌ Email sending
- ❌ Processing stabilization
- ❌ h265 encoding with regional resolution

</details>

### Gallery and Review Experience

_Improve the image gallery with better navigation, filtering, linking between views, and keyboard shortcuts._

**Effort:** XL | **Items:** 40 | **Status:** 4 tracked in GitHub; 36 untracked

**User stories:**
- As a taxonomist, I want to navigate between occurrence detail and session views with one click so I can review in context.
- As a field ecologist, I want to filter the gallery by species, confidence, and date so I find what I need quickly.

<details>
<summary>Underlying items (40)</summary>

- ❌ More quick buttons for processing & collections (x3)
- ❌ Processing convenience (buttons for process this night, process this collection) (x3)
- ❌ Default filter: lepidoptera (x2)
- 📋 Show best detection image in taxa view & occurrence view (x2) [[PR#1036](https://github.com/AMI-system/antenna/pull/1036)(MERGED); [PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED); [#560](https://github.com/AMI-system/antenna/issues/560)(OPEN); [PR#656](https://github.com/AMI-system/antenna/pull/656)(MERGED); [PR#566](https://github.com/AMI-system/antenna/pull/566)(MERGED)]
- 📋 Add column for best_identification to the occurrences view (optional, next to Taxon Determination column) (x2) [[PR#278](https://github.com/AMI-system/antenna/pull/278)(MERGED); [#560](https://github.com/AMI-system/antenna/issues/560)(OPEN); [PR#578](https://github.com/AMI-system/antenna/pull/578)(MERGED); [PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED); [PR#1036](https://github.com/AMI-system/antenna/pull/1036)(MERGED)]
- ❌ Filter/search by previous identifications (x2)
- 📋 Display user's seen occurrences in My Antenna [[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN)]
- ❌ Support experts in finding the correct species within the tool
- ❌ Consider mitigating psychological/positional bias in accepting proposed labels
- ❌ Filtering: Find a clear way to do it yet
- ❌ User interface (General Topic)
- ❌ Developing new UI components (new scrolling timeline)
- ❌ Notifications
- ❌ Notification system (Species of interest)
- ❌ Select project classifier etc. (More one-click options for processing the data)
- ❌ Labeling at scale - entomologists
- ❌ Alerts feature
- ❌ How can we make the data output more satisfactory?
- ❌ New filters: Which nights were captured by all stations? Filter out extra nights
- ❌ Alerts & notifications (region & species)
- ❌ "Species of Interest" feature
- ❌ Public splash page/landing page with a demo feature and interest form
- 📋 Make occurrences in collections clickable [[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN)]
- ❌ Improve explanations and add more contextual information about displayed data
- ❌ Allow drawing box to add missed moth in session review
- ❌ Add advanced filtering options
- ❌ Species page functionality/improvement
- ❌ Add alerts for species on user watch lists
- ❌ Add general notifications
- ❌ Ability to flag species outside classifier taxonomy
- ❌ Labeling interface - Bulk labeling from the grid view
- ❌ How to trigger post process steps from UI?
- ❌ Default filters & project settings
- ❌ Pipeline config from UI?
- ❌ Project Settings & feature flags
- ❌ Separating workflows per user category
- ❌ Make session detail more clear
- ❌ Showing what has been processed
- ❌ Labeling Interface Improvements (bulk labeling/editing bounding boxes)
- ❌ Labs page - Inference app and butterfly experiment

</details>

### Collections and Dynamic Datasets

_Rework image collections into dynamic, filter-based datasets for flexible grouping and batch operations._

**Effort:** XL | **Items:** 26 | **Status:** 7 partially implemented; 19 untracked

**User stories:**
- As a field ecologist, I want to create a dataset from filter criteria (date range, deployment, species) so I can batch-process specific subsets.
- As an ML researcher, I want dynamic collections so I can create training sets that update as new data arrives.

<details>
<summary>Underlying items (26)</summary>

- 🔧 Define if collections are reusable (design question) [[PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED)]
- 🔧 Implement default or automatic collections [[PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED)]
- 🔧 Clarify the term Collections with alternatives like Sample set Lists Datasets [[#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [#639](https://github.com/AMI-system/antenna/issues/639)(OPEN); [#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED)]
- 🔧 Continue to maintain comprehensive capabilities for managing and analyzing large datasets [[#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#1043](https://github.com/AMI-system/antenna/pull/1043)(MERGED); [PR#895](https://github.com/AMI-system/antenna/pull/895)(MERGED); [PR#897](https://github.com/AMI-system/antenna/pull/897)(MERGED); [PR#896](https://github.com/AMI-system/antenna/pull/896)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED); [PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [PR#598](https://github.com/AMI-system/antenna/pull/598)(MERGED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED)]
- 🔧 Will we always require collections for processing? [[#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED)]
- 🔧 Occurrence collections [[#763](https://github.com/AMI-system/antenna/issues/763)(OPEN); [#509](https://github.com/AMI-system/antenna/issues/509)(OPEN); [PR#184](https://github.com/AMI-system/antenna/pull/184)(MERGED); [PR#598](https://github.com/AMI-system/antenna/pull/598)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#604](https://github.com/AMI-system/antenna/pull/604)(MERGED); [#745](https://github.com/AMI-system/antenna/issues/745)(CLOSED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [#864](https://github.com/AMI-system/antenna/issues/864)(CLOSED); [PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED)]
- 🔧 Predefined collections / Dynamic presets [[PR#636](https://github.com/AMI-system/antenna/pull/636)(MERGED); [#730](https://github.com/AMI-system/antenna/issues/730)(OPEN); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [#297](https://github.com/AMI-system/antenna/issues/297)(CLOSED); [PR#375](https://github.com/AMI-system/antenna/pull/375)(MERGED); [PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [#451](https://github.com/AMI-system/antenna/issues/451)(OPEN); [PR#1067](https://github.com/AMI-system/antenna/pull/1067)(MERGED); [PR#283](https://github.com/AMI-system/antenna/pull/283)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED)]
- ❌ How can we make collections more natural in the workflow
- ❌ Define the Validation protocol and how to reach research-grade (x2) [[PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED)]
- ❌ Add processing support for project data
- ❌ Record if the suggestion was manually typed or accepted from a proposition
- ❌ Quality control of every stage before & after processing [[PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED)]
- ❌ Citation information
- ❌ Expose info about which model and when for each machine ID
- ❌ Data connector tool
- ❌ Add panama trap IDs
- ❌ Processing all data once model is ready & agreed on
- ❌ Help organizing & auditing the panama BCI projects
- ❌ Adding clear description to each project
- ❌ Filtering bad data (too small too blurry)
- ❌ Tracking of individuals (deduplication)
- ❌ Copying projects
- ❌ Use hierarchical folders for organizing cropped images by taxonomic order and family
- ❌ Add more fields for detailed hardware information
- ❌ Use iNaturalist (for validation/privacy) and Creative Commons as benchmarks [[PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED)]
- ❌ Michael to assist with data exports for new paper

</details>

### Taxonomy Hierarchy and Display

_Improved taxonomy tree navigation, display names, common names, and parent-child relationship management._

**Effort:** XL | **Items:** 24 | **Status:** 7 tracked in GitHub; 3 partially implemented; 14 untracked

**User stories:**
- As a taxonomist, I want to browse the taxonomy tree and see common names alongside scientific names.
- As a field ecologist, I want to navigate from a species to all its occurrences across my project.

<details>
<summary>Underlying items (24)</summary>

- ❌ Features for 'Pest species' (x3)
- 🔧 Add cryptic species status to the taxonomy database: Euceron species should always be determined to genus level (x2) [[#421](https://github.com/AMI-system/antenna/issues/421)(CLOSED); [PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED); [#655](https://github.com/AMI-system/antenna/issues/655)(OPEN); [#617](https://github.com/AMI-system/antenna/issues/617)(CLOSED); [#217](https://github.com/AMI-system/antenna/issues/217)(CLOSED)]
- 📋 Add size fields to the taxonomy database (fallback to parent size category). Avg. (x2) [[#655](https://github.com/AMI-system/antenna/issues/655)(OPEN)]
- 📋 Add is_cryptic field (to what rank) (x2) [[#857](https://github.com/AMI-system/antenna/issues/857)(OPEN)]
- 📋 Taxon rank rollup (genus, family level predictions) - never show a low confidence result (x2) [[PR#386](https://github.com/AMI-system/antenna/pull/386)(OPEN); [#421](https://github.com/AMI-system/antenna/issues/421)(CLOSED); [#384](https://github.com/AMI-system/antenna/issues/384)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [#864](https://github.com/AMI-system/antenna/issues/864)(CLOSED)]
- 📋 Taxonomy management (External sources/managing taxa/lists/synonyms) (x2) [[#655](https://github.com/AMI-system/antenna/issues/655)(OPEN); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED)]
- ❌ Importing - Taxa lists (x2)
- ❌ Interface for managing species
- 🔧 Add a field to the taxa DB for unidentifiable by image alone with relation to similar taxa [[PR#244](https://github.com/AMI-system/antenna/pull/244)(MERGED); [#655](https://github.com/AMI-system/antenna/issues/655)(OPEN)]
- ❌ Add Not Identifiable and Lepidoptera entry IDs
- ❌ Features for 'Species of conservation concern' / 'Species of risk'
- ❌ Features for 'Non-native' species
- ❌ Provisional lists of species (regional lists)
- 📋 Rank roll-ups [[#857](https://github.com/AMI-system/antenna/issues/857)(OPEN)]
- ❌ Remove species that should not be classified (get checklists from experts)
- ❌ Taxonomy database with our own metadata (Cryptic status, Size or size category, Model performance/training info)
- 🔧 Add fields for barcode bin numbers to assist with species identification [[#216](https://github.com/AMI-system/antenna/issues/216)(CLOSED); [PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED); [#560](https://github.com/AMI-system/antenna/issues/560)(OPEN)]
- 📋 Allow viewing IDs by genus/family/etc. [[#384](https://github.com/AMI-system/antenna/issues/384)(OPEN)]
- 📋 Rank rollups [[#857](https://github.com/AMI-system/antenna/issues/857)(OPEN)]
- ❌ Taxonomy (Hierarchical categories/Many taxonomic ranks)
- ❌ Taxonomy API & shared database
- ❌ Integrate support for barcode bin numbers for species without traditional names
- ❌ Ask Chris for list of any all categories of interest
- ❌ How much freedom do we give projects & users for Taxonomy

</details>

### Phenology and Abundance Charts

_Visualize species occurrence over time — flight periods, seasonal patterns, abundance trends, co-occurrence._

**Effort:** XL | **Items:** 21 | **Status:** 21 untracked

**User stories:**
- As a field ecologist, I want phenology charts showing when species appear so I can compare across years.
- As a conservation decision-maker, I want abundance trend graphs so I can assess population changes.

<details>
<summary>Underlying items (21)</summary>

- ❌ X-axis for Seasonal flight charts should use dates
- ❌ Address caveat: dynamic charts only show what is processed (but make it look like everything is processed)
- ❌ Default charts feature
- ❌ Some basic analysis built in to compare these species of interest
- ❌ Michael to assist with analysis and charts for new paper
- ❌ Show evalutation stats while validating
- ❌ Configure overview stats for a project (Needs more information and user discussions)
- ❌ See charts for troubleshooting (not analysis) (Needs more information and user discussions)
- ❌ Showing some evaluation & statistics within the UI / Summary metrics as you go
- ❌ Default to order level & wider metrics
- ❌ Visualizations / aggregation (flight charts) BUT need to only show results we are confident for
- ❌ Continue to maintain and enhance automatic visualizations and data organization features
- ❌ Features for data analysis: Flight charts and maps with data
- ❌ The ability to see where the problems are happening
- ❌ Summary metrics as you go (for troubleshooting/improving results)
- ❌ Time series images (specific automated captured)
- ❌ See detections grouped as tracks (UI and data structures prepared, logic in progress)
- ❌ Change 'Captures per hour' to 'Average captures per hour per night'
- ❌ Change 'Detections per hour' to 'Detections per hour per night on average'
- ❌ Bug: Counts per deployment
- ❌ Summary shows capture/hr and sessions/month - suggest other relevant data

</details>

### Darwin Core and Data Export

_Export occurrence data in Darwin Core, CSV, and other formats for GBIF submission and ecological analysis._

**Effort:** L | **Items:** 18 | **Status:** 2 tracked in GitHub; 1 partially implemented; 15 untracked

**User stories:**
- As a field ecologist, I want to export my data in Darwin Core format so I can submit it to GBIF.
- As a project manager, I want CSV exports with flexible column selection so I can use the data in R or Python.
- As an ML researcher, I want to export training data with annotations for model development.

<details>
<summary>Underlying items (18)</summary>

- ❌ Data Exports (Yves needed for writing grant)
- ❌ Exports & Downloads (Self-service feature remaining)
- 📋 Darwincore export and Export format for ML retraining (x8) [[#298](https://github.com/AMI-system/antenna/issues/298)(OPEN)]
- ❌ Exporting data (General Topic)
- ❌ API (General Topic)
- ❌ Exports
- ❌ Data access for fine-tuning - ML research
- ❌ Data Exports: Darwin Core for biologists and bioinformatics people
- ❌ Data Exports: COCO/YOLO formats for re-training purposes (ML researchers)
- 🔧 Implement a Taxa List Filter and support Darwin Core Export Format [[#298](https://github.com/AMI-system/antenna/issues/298)(OPEN); [PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [#720](https://github.com/AMI-system/antenna/issues/720)(CLOSED)]
- ❌ Implement export options
- ❌ Replicate desktop/offline version export options
- ❌ Provide easier method to export and organize cropped images hierarchically by taxonomy
- ❌ Add missing fields related to images when exporting to CSV
- 📋 Download X amount of photos for a species list with high confidence [[#933](https://github.com/AMI-system/antenna/issues/933)(OPEN)]
- ❌ New export format geared toward ML with previous predictions/corrected IDs
- ❌ Exports to DARWIN core
- ❌ Export Formats (Darwin Core/COCO/YOLO formats)

</details>

### Permissions and Team Roles

_Fine-grained roles (viewer, reviewer, admin) and object-level permissions for multi-team collaboration._

**Effort:** L | **Items:** 13 | **Status:** 13 untracked

**User stories:**
- As a project manager, I want to grant reviewers access to verify identifications without being able to change project settings.
- As an admin, I want to manage team membership and permissions per project so each team controls their own data.

<details>
<summary>Underlying items (13)</summary>

- ❌ Implement Private projects (MVP feature)
- ❌ Open to the public for read-only review (Next 6 months)
- ❌ Multiple projects & users
- ❌ Make it clear who contacts are for each project (the initiator and the hands-on/technical contacts)
- ❌ Project manager (role/tooling)
- ❌ Allow inviting a collaborator to confirm IDs
- ❌ Use Roles system to hide/show features and default ordering
- ❌ Implement multi-level (Curator expert etc.) point-based validation/curation (eButterfly model)
- ❌ Obfuscating exact device location (Sensitive/Fuzzy privacy)
- ❌ Implement fine-grained Job Permissions based on job types (e.g., ML, export, sync)
- ❌ Orgs & Per-project permissions (Mohamed's work)
- ❌ Allow users to invite categories
- ❌ Support for application tokens that are not tied to a specific user

</details>

### Deployment and Event Management

_Better tools for managing monitoring stations, sites, devices, and temporal event grouping._

**Effort:** L | **Items:** 13 | **Status:** 2 tracked in GitHub; 10 partially implemented; 1 untracked

**User stories:**
- As a field ecologist, I want to manage multiple camera stations with their locations and time periods from the UI.
- As a project manager, I want to see which deployments have recent data and which need attention.

<details>
<summary>Underlying items (13)</summary>

- 🔧 Registration & map of camera deployments (metadata) [[#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [PR#492](https://github.com/AMI-system/antenna/pull/492)(MERGED); [PR#152](https://github.com/AMI-system/antenna/pull/152)(MERGED); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [#343](https://github.com/AMI-system/antenna/issues/343)(CLOSED); [#258](https://github.com/AMI-system/antenna/issues/258)(OPEN); [PR#158](https://github.com/AMI-system/antenna/pull/158)(MERGED); [#611](https://github.com/AMI-system/antenna/issues/611)(OPEN)]
- 🔧 Occurrence tracking [[#457](https://github.com/AMI-system/antenna/issues/457)(OPEN); [PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED); [PR#665](https://github.com/AMI-system/antenna/pull/665)(MERGED); [PR#488](https://github.com/AMI-system/antenna/pull/488)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED); [PR#659](https://github.com/AMI-system/antenna/pull/659)(MERGED); [PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#429](https://github.com/AMI-system/antenna/pull/429)(MERGED); [#832](https://github.com/AMI-system/antenna/issues/832)(OPEN); [#833](https://github.com/AMI-system/antenna/issues/833)(CLOSED)]
- 🔧 Help renaming files from new camera [[PR#230](https://github.com/AMI-system/antenna/pull/230)(MERGED); [PR#325](https://github.com/AMI-system/antenna/pull/325)(MERGED); [PR#366](https://github.com/AMI-system/antenna/pull/366)(MERGED); [#258](https://github.com/AMI-system/antenna/issues/258)(OPEN); [PR#158](https://github.com/AMI-system/antenna/pull/158)(MERGED); [PR#1068](https://github.com/AMI-system/antenna/pull/1068)(MERGED); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED); [PR#1002](https://github.com/AMI-system/antenna/pull/1002)(MERGED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#492](https://github.com/AMI-system/antenna/pull/492)(MERGED)]
- 🔧 Provide a more dynamic way to handle sessions and timestamps [[#224](https://github.com/AMI-system/antenna/issues/224)(CLOSED); [#237](https://github.com/AMI-system/antenna/issues/237)(OPEN); [#906](https://github.com/AMI-system/antenna/issues/906)(OPEN); [PR#1073](https://github.com/AMI-system/antenna/pull/1073)(MERGED); [PR#908](https://github.com/AMI-system/antenna/pull/908)(MERGED); [PR#568](https://github.com/AMI-system/antenna/pull/568)(MERGED); [PR#362](https://github.com/AMI-system/antenna/pull/362)(MERGED); [#206](https://github.com/AMI-system/antenna/issues/206)(CLOSED); [#1063](https://github.com/AMI-system/antenna/issues/1063)(OPEN); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED)]
- 🔧 Implement method for bulk updating of incorrect timestamps [[#273](https://github.com/AMI-system/antenna/issues/273)(OPEN); [#625](https://github.com/AMI-system/antenna/issues/625)(OPEN); [#1107](https://github.com/AMI-system/antenna/issues/1107)(OPEN); [PR#1105](https://github.com/AMI-system/antenna/pull/1105)(MERGED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#905](https://github.com/AMI-system/antenna/pull/905)(MERGED); [PR#829](https://github.com/AMI-system/antenna/pull/829)(MERGED); [PR#809](https://github.com/AMI-system/antenna/pull/809)(MERGED); [PR#781](https://github.com/AMI-system/antenna/pull/781)(MERGED)]
- 🔧 Develop dynamic session partitioning for better data visualization and analysis [[PR#542](https://github.com/AMI-system/antenna/pull/542)(MERGED); [#410](https://github.com/AMI-system/antenna/issues/410)(CLOSED); [PR#401](https://github.com/AMI-system/antenna/pull/401)(MERGED); [#273](https://github.com/AMI-system/antenna/issues/273)(OPEN); [PR#189](https://github.com/AMI-system/antenna/pull/189)(MERGED); [#399](https://github.com/AMI-system/antenna/issues/399)(CLOSED); [PR#568](https://github.com/AMI-system/antenna/pull/568)(MERGED); [PR#453](https://github.com/AMI-system/antenna/pull/453)(MERGED); [PR#347](https://github.com/AMI-system/antenna/pull/347)(MERGED); [PR#205](https://github.com/AMI-system/antenna/pull/205)(MERGED)]
- 🔧 Add context pictures of devices in the field [[PR#325](https://github.com/AMI-system/antenna/pull/325)(MERGED); [PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED); [PR#152](https://github.com/AMI-system/antenna/pull/152)(MERGED); [#958](https://github.com/AMI-system/antenna/issues/958)(OPEN); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [PR#1068](https://github.com/AMI-system/antenna/pull/1068)(MERGED); [PR#1002](https://github.com/AMI-system/antenna/pull/1002)(MERGED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#492](https://github.com/AMI-system/antenna/pull/492)(MERGED)]
- 🔧 Possibility of shorter deployments [[#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#158](https://github.com/AMI-system/antenna/pull/158)(MERGED); [#611](https://github.com/AMI-system/antenna/issues/611)(OPEN); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [#258](https://github.com/AMI-system/antenna/issues/258)(OPEN); [PR#1068](https://github.com/AMI-system/antenna/pull/1068)(MERGED); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED)]
- 🔧 Continue to maintain the ability to add and edit information about devices and deployments [[#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED); [#714](https://github.com/AMI-system/antenna/issues/714)(OPEN); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#325](https://github.com/AMI-system/antenna/pull/325)(MERGED); [PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED); [PR#152](https://github.com/AMI-system/antenna/pull/152)(MERGED)]
- 🔧 Speed up deployments list? [[#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#307](https://github.com/AMI-system/antenna/issues/307)(OPEN); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED); [PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED); [#611](https://github.com/AMI-system/antenna/issues/611)(OPEN); [#304](https://github.com/AMI-system/antenna/issues/304)(OPEN); [#258](https://github.com/AMI-system/antenna/issues/258)(OPEN); [PR#1065](https://github.com/AMI-system/antenna/pull/1065)(MERGED); [PR#1002](https://github.com/AMI-system/antenna/pull/1002)(MERGED)]
- 📋 Display Images for deployments [[PR#353](https://github.com/AMI-system/antenna/pull/353)(MERGED); [#714](https://github.com/AMI-system/antenna/issues/714)(OPEN); [#439](https://github.com/AMI-system/antenna/issues/439)(OPEN)]
- 📋 Expose specific data source subdirectory in Deployment edit [[#1047](https://github.com/AMI-system/antenna/issues/1047)(OPEN); [PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED)]
- ❌ Fix issue with re-choosing Site & Device when editing a Deployment

</details>

### Developer and API Documentation

_Technical docs for building integrations, custom processing services, and contributing to Antenna._

**Effort:** M | **Items:** 7 | **Status:** 4 partially implemented; 3 untracked

**User stories:**
- As an ML researcher, I want API docs so I can build a custom processing service that integrates with Antenna.
- As a developer, I want contributor guidelines so I can add features to the open-source project.

<details>
<summary>Underlying items (7)</summary>

- 🔧 Browser-based regression / integration tests (Cypress/Playwright) (x2) [[#852](https://github.com/AMI-system/antenna/issues/852)(OPEN); [#708](https://github.com/AMI-system/antenna/issues/708)(OPEN); [PR#586](https://github.com/AMI-system/antenna/pull/586)(MERGED); [PR#675](https://github.com/AMI-system/antenna/pull/675)(MERGED); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED); [PR#647](https://github.com/AMI-system/antenna/pull/647)(MERGED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED); [#667](https://github.com/AMI-system/antenna/issues/667)(CLOSED); [#377](https://github.com/AMI-system/antenna/issues/377)(OPEN); [PR#980](https://github.com/AMI-system/antenna/pull/980)(MERGED)]
- ❌ New sprint schedule: 3 weeks development, 1 week for documentation and planning
- 🔧 More full stack dev, easier integration from ML experiments to platform [[#504](https://github.com/AMI-system/antenna/issues/504)(OPEN); [#816](https://github.com/AMI-system/antenna/issues/816)(OPEN); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED); [PR#647](https://github.com/AMI-system/antenna/pull/647)(MERGED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED); [#667](https://github.com/AMI-system/antenna/issues/667)(CLOSED); [#377](https://github.com/AMI-system/antenna/issues/377)(OPEN); [PR#980](https://github.com/AMI-system/antenna/pull/980)(MERGED); [PR#675](https://github.com/AMI-system/antenna/pull/675)(MERGED); [PR#666](https://github.com/AMI-system/antenna/pull/666)(MERGED)]
- 🔧 Inference page for easily testing all models (without project setup, etc) [[#533](https://github.com/AMI-system/antenna/issues/533)(CLOSED); [#708](https://github.com/AMI-system/antenna/issues/708)(OPEN); [PR#675](https://github.com/AMI-system/antenna/pull/675)(MERGED); [PR#980](https://github.com/AMI-system/antenna/pull/980)(MERGED); [#816](https://github.com/AMI-system/antenna/issues/816)(OPEN); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED); [PR#647](https://github.com/AMI-system/antenna/pull/647)(MERGED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED); [#667](https://github.com/AMI-system/antenna/issues/667)(CLOSED); [#377](https://github.com/AMI-system/antenna/issues/377)(OPEN)]
- 🔧 Dedicated interface for testing models (e.g. using Streamlit or Solara) [[#708](https://github.com/AMI-system/antenna/issues/708)(OPEN); [#816](https://github.com/AMI-system/antenna/issues/816)(OPEN); [PR#980](https://github.com/AMI-system/antenna/pull/980)(MERGED); [PR#835](https://github.com/AMI-system/antenna/pull/835)(MERGED); [PR#647](https://github.com/AMI-system/antenna/pull/647)(MERGED); [#749](https://github.com/AMI-system/antenna/issues/749)(CLOSED); [#667](https://github.com/AMI-system/antenna/issues/667)(CLOSED); [#377](https://github.com/AMI-system/antenna/issues/377)(OPEN); [PR#675](https://github.com/AMI-system/antenna/pull/675)(MERGED); [PR#666](https://github.com/AMI-system/antenna/pull/666)(MERGED)]
- ❌ Circle back to OpenAPI docs to allow researchers to query occurrences in R
- ❌ Standardizing the model APIs

</details>

### Self-Hosting Documentation

_Installation guides, configuration docs, and one-click deploy options for community self-hosting._

**Effort:** S | **Items:** 1 | **Status:** 1 untracked

**User stories:**
- As a university IT admin, I want clear installation docs so I can deploy Antenna for our ecology department.
- As a community user, I want a one-click deploy option (Digital Ocean, etc.) so I can run my own instance.

<details>
<summary>Underlying items (1)</summary>

- ❌ Antenna (self-hosted version)

</details>

## Later / Someday — 7 cards, 125 items

_Important but not urgent. Coarser grouping — these get refined when they move closer._

### Community Building

_Forums, shared resources, community events, and collaboration tools for the broader Antenna ecosystem._

**Effort:** XL | **Items:** 49 | **Status:** 49 untracked

**User stories:**
- As a community member, I want a forum to share experiences and help others set up their monitoring programs.
- As a project manager, I want to discover and connect with other teams using Antenna in my region.

<details>
<summary>Underlying items (49)</summary>

- ❌ New release on GitHub (x2)
- ❌ Add to Wildlabs inventory (x2)
- ❌ Mailing list & regular updates (x2)
- ❌ Provide an interface for citizen scientists to learn & contribute.
- ❌ Citizen Science Version/Features
- ❌ Place for users to add their experience
- ❌ LepiNoc (citizen science) - different requirements/mobile app
- ❌ Get contribution agreements in writing
- ❌ Define how credit will be given
- ❌ Decide on the platform name
- ❌ Online platform for ML-assisted monitoring of arthropods (Agile software pipeline new algorithms/research friendly/efficient UI)
- ❌ Implement sustainable business/partner model
- ❌ Functionality needs for specific projects (General Topic)
- ❌ Assign and train a person at each partner org (Insectarium)
- ❌ Assigning someone from Antenna to be the main contact for each project
- ❌ Enforcing the use of the antenna email and add relevant people as recipients
- ❌ Regular call for all partners using Antenna
- ❌ Sending out a form to be filled out before each meeting
- ❌ Find project & partner manager for Antenna
- ❌ Training others to respond to partners
- ❌ Find intern and train on basic tasks
- ❌ Training sessions for our own staff
- ❌ Sustainability leadership and financial model
- ❌ Getting anxious for something to be working & finished soon
- ❌ Formalize Strategic Direction: Hosted Platform vs. Enterprise Portals vs. Open Source Only
- ❌ Formally select Option A (Client Portals) as the Q1 Strategic Alignment goal (based on lean team)
- ❌ Create a user matrix and a feature matrix (for Jan 27th meeting)
- ❌ Define Milestones for 2026 (What do we want by April/July?)
- ❌ Keep track of email correspondence with current and new contacts
- ❌ Planning for meetings (accounted for)
- ❌ A side goal of the platform is to increase engagement in the observation of insects.
- ❌ Enable & expedite new formal research.
- ❌ Monetization strategy/pricing (to put into grants)
- ❌ Continue to foster platform's openness and potential for collaboration
- ❌ Need for continuous funding to maintain and expand monitoring projects
- ❌ Mandatory Decision: Direction of platform (Client portals vs Central platform)
- ❌ Platform Vision/Strategy (defining goals & milestones for 2026)
- ❌ Which features before April 2026?
- ❌ Which need to be self service from a centrally hosted platform?
- ❌ Which need a planning & prototype sprint
- ❌ Which features are MVP vs production-ready?
- ❌ Which features need to be self-service vs admin-only?
- ❌ Are we trying to make an app for everyone? Supporting 2-3 partners?
- ❌ Simplicity vs. feature richness
- ❌ Which partner types? Which partner types need self-service?
- ❌ NRCAN (government/landscape scale) - custom deployment with support?
- ❌ Mothitor project/Maxim's projects (research labs) - self-service priority
- ❌ Which features empower & accelerate teams in what they already do?
- ❌ Project manager

</details>

### Advanced ML Features

_Clustering support, multi-model ensembles, active learning loops, and advanced post-processing._

**Effort:** XL | **Items:** 40 | **Status:** 3 tracked in GitHub; 10 partially implemented; 27 untracked

**User stories:**
- As an ML researcher, I want to run multiple models and ensemble their results for better accuracy.
- As a project manager, I want the system to actively learn from corrections to improve over time.

<details>
<summary>Underlying items (40)</summary>

- 🔧 Support for unknown species (clustering) [[PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#832](https://github.com/AMI-system/antenna/pull/832)(OPEN); [#775](https://github.com/AMI-system/antenna/issues/775)(OPEN); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED)]
- 🔧 Option to use model consensus instead of top confidence score (consensus between global & regional model or versions of panama models) [[PR#1029](https://github.com/AMI-system/antenna/pull/1029)(MERGED); [PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [PR#944](https://github.com/AMI-system/antenna/pull/944)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#603](https://github.com/AMI-system/antenna/pull/603)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED)]
- 🔧 Integrate Out-of-Distribution (OOD) features for data curation (tagging, moving occurrences between clusters) [[PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED); [PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)]
- 📋 OOD Feature Refinement (for "unexpected species" flagging) [[PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#811](https://github.com/AMI-system/antenna/issues/811)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED)]
- 🔧 Continuous OOD detection (combined with clustering; how to remove the OOD species that have been verified) [[PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN)]
- 🔧 Out-of-Distribution (OOD) feature (Mockups, protocol for detecting new species, feature vectors, Yuyan's model) [[PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#670](https://github.com/AMI-system/antenna/pull/670)(MERGED)]
- 📋 Few-shot learning for adding species [[#767](https://github.com/AMI-system/antenna/issues/767)(OPEN); [PR#911](https://github.com/AMI-system/antenna/pull/911)(CLOSED); [#290](https://github.com/AMI-system/antenna/issues/290)(CLOSED)]
- 🔧 Geofencing [[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED)]
- 🔧 Labeling behavior poses and other attributes [[PR#691](https://github.com/AMI-system/antenna/pull/691)(MERGED)]
- 🔧 Explainable AI - What features did you use to ID this species? Teaching the user. [[PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#670](https://github.com/AMI-system/antenna/pull/670)(MERGED); [#875](https://github.com/AMI-system/antenna/issues/875)(OPEN); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#816](https://github.com/AMI-system/antenna/pull/816)(OPEN); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN); [#804](https://github.com/AMI-system/antenna/issues/804)(CLOSED)]
- 📋 Image classifier from infrared or hyper-spectral images [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#762](https://github.com/AMI-system/antenna/pull/762)(MERGED)]
- 🔧 Fast object detector edge deployments [[#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#656](https://github.com/AMI-system/antenna/pull/656)(MERGED); [PR#602](https://github.com/AMI-system/antenna/pull/602)(MERGED); [PR#596](https://github.com/AMI-system/antenna/pull/596)(MERGED); [PR#285](https://github.com/AMI-system/antenna/pull/285)(MERGED); [PR#115](https://github.com/AMI-system/antenna/pull/115)(MERGED)]
- 🔧 Do we really need a species level classifier? For which species? For which purposes? [[#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#762](https://github.com/AMI-system/antenna/pull/762)(MERGED)]
- ❌ Model suggestions for impossible-to-ID species (confusion matrix) and handling of cryptic species split geographically
- ❌ Distinguish between no more fine-grained labels available and need for more information to label prediction limitations
- ❌ Implement Better algorithms (MVP feature)
- ❌ ML backend (General Topic) [[#445](https://github.com/AMI-system/antenna/issues/445)(CLOSED)]
- ❌ Improving quality of results - and what gets an ID at all
- ❌ How can we get to research grade automatically? For the ones we can
- ❌ LORA adapter that is trained on a small amount of data and appended at inference time for improving results
- ❌ Model zoo for insects [[#804](https://github.com/AMI-system/antenna/issues/804)(CLOSED)]
- ❌ Is Antenna a model zoo? Or just an index of what registered & available
- ❌ Working on the "secret sauce" methods to improve results for insects - external stats
- ❌ Priors and adding statistical models (Logistic binning Shannon entropy)
- ❌ Identify "Tricky" species (cannot identify the species with visual information only)
- ❌ Multiple objects in one bounding box
- ❌ Demo Flatbug
- ❌ Demo other segmentation algorithms
- ❌ Transparency: How many images and what images was the model trained on?
- ❌ Transparency: We don't know about this species
- ❌ Transparency: What are the stupid errors
- ❌ Somehow display which species the model is better or worse at
- ❌ Re-training panama model with fewer
- ❌ How to do process efficiently in batch (similarity model, etc)
- ❌ Dataset transparency (show training data species/images for each model)
- ❌ Build a retraining workflow (use verified data to improve model)
- ❌ Continue to maintain and enhance the integration of multiple algorithms for species identification
- ❌ Allow ability to resume job where it failed [[#874](https://github.com/AMI-system/antenna/issues/874)(CLOSED); [PR#233](https://github.com/AMI-system/antenna/pull/233)(CLOSED)]
- ❌ Test semi-automated training (active learning) of models
- ❌ Size estimator with annotations (from normal photos, verified in Bold, iNat) (x2)

</details>

### Research and Experimental Features

_Exploratory work: new ecological metrics, experimental UI patterns, academic collaboration features._

**Effort:** L | **Items:** 18 | **Status:** 1 tracked in GitHub; 2 partially implemented; 15 untracked

**User stories:**
- As an ML researcher, I want experimental features behind feature flags so I can test ideas without affecting production users.
- As a field ecologist, I want to pilot new analysis methods on my data before they become standard features.

<details>
<summary>Underlying items (18)</summary>

- ❌ Metrics for scaling - how much human validation is necessary to trust the model
- 📋 Plan to review data only at end of deployment [[#307](https://github.com/AMI-system/antenna/issues/307)(OPEN)]
- 🔧 Importance of long-term data for ecological and taxonomic research [[#916](https://github.com/AMI-system/antenna/issues/916)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#1077](https://github.com/AMI-system/antenna/pull/1077)(MERGED); [PR#550](https://github.com/AMI-system/antenna/pull/550)(MERGED); [PR#247](https://github.com/AMI-system/antenna/pull/247)(MERGED); [PR#203](https://github.com/AMI-system/antenna/pull/203)(MERGED); [#1015](https://github.com/AMI-system/antenna/issues/1015)(OPEN); [#298](https://github.com/AMI-system/antenna/issues/298)(OPEN); [#985](https://github.com/AMI-system/antenna/issues/985)(CLOSED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED)]
- ❌ Estimation of physical size. Biomass.
- ❌ How can we confidently scale these systems beyond what humans can do?
- 🔧 Experimenting with fine-grained classification [[#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [PR#741](https://github.com/AMI-system/antenna/pull/741)(MERGED); [PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#574](https://github.com/AMI-system/antenna/pull/574)(MERGED); [PR#241](https://github.com/AMI-system/antenna/pull/241)(MERGED); [#628](https://github.com/AMI-system/antenna/issues/628)(CLOSED); [#621](https://github.com/AMI-system/antenna/issues/621)(CLOSED)]
- ❌ Common challenges - two lists of classes: species that exist and species that you can identify visually from a top-down image.
- ❌ Is this any more efficient than traditional monitoring [[PR#352](https://github.com/AMI-system/antenna/pull/352)(CLOSED)]
- ❌ Building a dataset of moth size information
- ❌ Ask Chris for list of any, all categories of interest
- ❌ Analyze morphological traits and temporal patterns, using the data we have
- ❌ What can we do with the data we have?
- ❌ Comparison with traditional monitoring data (BCI)
- ❌ Clearly define the issues we see
- ❌ Propose projects to work on new methods
- ❌ Concern about handling incorrect timestamps from faulty real-time clocks
- ❌ Skeptical about speed and accuracy of integrating DNA barcoding data
- ❌ Summary metrics - species richness. The accuracy of the species richness is 90% even when the classification accuracy is 60%.

</details>

### Ecosystem Integrations

_Connect with iNaturalist, GBIF, and external ML platforms for data exchange and community science._

**Effort:** L | **Items:** 10 | **Status:** 3 tracked in GitHub; 7 untracked

**User stories:**
- As a community scientist, I want to sync observations with iNaturalist so both platforms benefit.
- As a project manager, I want automatic GBIF submission so our data is publicly discoverable.

<details>
<summary>Underlying items (10)</summary>

- 📋 Implement connection to GBIF (MVP feature) [[#508](https://github.com/AMI-system/antenna/issues/508)(OPEN)]
- 📋 Which deployments which data are published to GBIF [[#508](https://github.com/AMI-system/antenna/issues/508)(OPEN)]
- ❌ Suggests Zenodo for dataset publishing
- ❌ Integrate or share data between software and ARISE
- 📋 Publishing Zenodo DOI [[#508](https://github.com/AMI-system/antenna/issues/508)(OPEN)]
- ❌ Button to publish a single observation to iNaturalist?
- ❌ Create a user for each model on iNaturalist?
- ❌ Implement querying images for inference from ADC API and POSTing results back
- ❌ Plan for an R package to interface the API for plots stats etc.
- ❌ Python & R clients to interact with data already in Antenna

</details>

### Multi-Tenant and Cloud Scaling

_Support multiple organizations on shared infrastructure with proper isolation and resource management._

**Effort:** M | **Items:** 5 | **Status:** 5 untracked

**User stories:**
- As an admin, I want to host multiple organizations on one deployment with proper data isolation.
- As a cloud operator, I want auto-scaling so the platform handles load spikes during processing.

<details>
<summary>Underlying items (5)</summary>

- ❌ Move to managed hosting (if centralized system is desired)
- ❌ Transition to automated and centralized instance management
- ❌ Explore Kubernetes if limited by Docker Swarm
- ❌ Need consumer service to scale up (Suggested: Rodrigo)
- ❌ Investigate/Implement containerisation for massively parallel (10000 core+) image processing

</details>

### Pollinator and General Detection

_Expand beyond moths to pollinators, general insects, and broader ecological monitoring use cases._

**Effort:** S | **Items:** 2 | **Status:** 2 untracked

**User stories:**
- As a field ecologist, I want to detect pollinators visiting flowers so I can study plant-pollinator interactions.
- As a conservation decision-maker, I want general insect monitoring data, not just moths.

<details>
<summary>Underlying items (2)</summary>

- ❌ Other invertebrates - other nocturnals, and day-time polinators
- ❌ All arthropods model (global insects, spiders, etc)

</details>

### Non-Time-Series Data Support

_Support lab microscopes, specimen drawers, and other non-camera-trap image sources._

**Effort:** S | **Items:** 1 | **Status:** 1 untracked

**User stories:**
- As an entomologist, I want to process specimen drawer photos so I can digitize museum collections.
- As an ML researcher, I want to use Antenna for lab microscope images so one platform handles all insect imaging.

<details>
<summary>Underlying items (1)</summary>

- ❌ Implement same data process for acoustic recordings

</details>

## Already Done (Reference) — 1 cards, 109 items

_Not on the board. Summary of shipped capabilities for context._

**109 items** already shipped across these categories:

- **Analytics/Viz** (9 items)
- **Data-Management** (10 items)
- **DevEx** (1 items)
- **Export/Interop** (2 items)
- **Infrastructure** (14 items)
- **ML/AI** (12 items)
- **Permissions/Auth** (7 items)
- **Research** (3 items)
- **Taxonomy** (2 items)
- **UI/UX** (49 items)

<details>
<summary>Show completed items</summary>

### Analytics/Viz

- Antenna features to 'Generate compound flight chart per taxa list' — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Top species chart to overview page — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Flight charts for taxa & taxa lists — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Add same charts (Average captures/detections per hour per night) but filtered by one specific species — _[PR#189](https://github.com/AMI-system/antenna/pull/189)(MERGED)_
- Add multiple lines to compare multiple species (compare flight times) on charts — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Be able to select any higher taxon group for filtering charts — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Charts & Trends (Top species, flight chart/flying patterns - high-level summaries) — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_
- Show time series of images taken — _[PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED)_
- Data Visualization (charts/stats/flight charts for taxa) — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED)_

### Data-Management

- Importing - Data processed externally (Detections/Predictions) — _[#682](https://github.com/AMI-system/antenna/issues/682)(CLOSED); [#672](https://github.com/AMI-system/antenna/issues/672)(CLOSED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#1036](https://github.com/AMI-system/antenna/pull/1036)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#765](https://github.com/AMI-system/antenna/pull/765)(MERGED); [PR#596](https://github.com/AMI-system/antenna/pull/596)(MERGED); [PR#203](https://github.com/AMI-system/antenna/pull/203)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [#706](https://github.com/AMI-system/antenna/issues/706)(CLOSED)_
- Define if collections are absolutely needed or more like job settings (design question) — _[PR#891](https://github.com/AMI-system/antenna/pull/891)(MERGED); [#718](https://github.com/AMI-system/antenna/issues/718)(CLOSED); [PR#612](https://github.com/AMI-system/antenna/pull/612)(MERGED); [#716](https://github.com/AMI-system/antenna/issues/716)(CLOSED); [PR#657](https://github.com/AMI-system/antenna/pull/657)(MERGED); [PR#626](https://github.com/AMI-system/antenna/pull/626)(MERGED); [PR#286](https://github.com/AMI-system/antenna/pull/286)(MERGED); [PR#315](https://github.com/AMI-system/antenna/pull/315)(MERGED); [PR#632](https://github.com/AMI-system/antenna/pull/632)(MERGED); [#614](https://github.com/AMI-system/antenna/issues/614)(CLOSED)_
- Fix missing sessions on occurrences - can we ensure sessions are grouped before processing — _[PR#794](https://github.com/AMI-system/antenna/pull/794)(MERGED); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED); [#329](https://github.com/AMI-system/antenna/issues/329)(CLOSED); [PR#692](https://github.com/AMI-system/antenna/pull/692)(MERGED); [PR#620](https://github.com/AMI-system/antenna/pull/620)(MERGED); [#651](https://github.com/AMI-system/antenna/issues/651)(CLOSED); [#443](https://github.com/AMI-system/antenna/issues/443)(CLOSED); [PR#691](https://github.com/AMI-system/antenna/pull/691)(MERGED); [#403](https://github.com/AMI-system/antenna/issues/403)(CLOSED); [PR#296](https://github.com/AMI-system/antenna/pull/296)(MERGED)_
- Importing Taxa lists, Data processed externally, Captures (public HTTP urls) — _[PR#203](https://github.com/AMI-system/antenna/pull/203)(MERGED); [#864](https://github.com/AMI-system/antenna/issues/864)(CLOSED); [#745](https://github.com/AMI-system/antenna/issues/745)(CLOSED); [#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED); [PR#838](https://github.com/AMI-system/antenna/pull/838)(MERGED); [PR#292](https://github.com/AMI-system/antenna/pull/292)(MERGED); [#998](https://github.com/AMI-system/antenna/issues/998)(CLOSED); [#796](https://github.com/AMI-system/antenna/issues/796)(CLOSED); [#393](https://github.com/AMI-system/antenna/issues/393)(CLOSED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED)_
- Develop a formula to extract year (YEAR function) from the date in column A to fill column C (Example Row) — _[PR#809](https://github.com/AMI-system/antenna/pull/809)(MERGED); [PR#1105](https://github.com/AMI-system/antenna/pull/1105)(MERGED); [PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#905](https://github.com/AMI-system/antenna/pull/905)(MERGED); [PR#829](https://github.com/AMI-system/antenna/pull/829)(MERGED); [PR#781](https://github.com/AMI-system/antenna/pull/781)(MERGED); [PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [PR#756](https://github.com/AMI-system/antenna/pull/756)(MERGED)_
- Daily morning SD cards collection of the entocam — _[PR#584](https://github.com/AMI-system/antenna/pull/584)(MERGED); [PR#895](https://github.com/AMI-system/antenna/pull/895)(MERGED); [PR#896](https://github.com/AMI-system/antenna/pull/896)(MERGED); [PR#800](https://github.com/AMI-system/antenna/pull/800)(MERGED); [PR#598](https://github.com/AMI-system/antenna/pull/598)(MERGED); [PR#222](https://github.com/AMI-system/antenna/pull/222)(MERGED); [#639](https://github.com/AMI-system/antenna/issues/639)(OPEN); [#548](https://github.com/AMI-system/antenna/issues/548)(CLOSED); [PR#1043](https://github.com/AMI-system/antenna/pull/1043)(MERGED); [#650](https://github.com/AMI-system/antenna/issues/650)(CLOSED)_
- Reinstall them — _[PR#1060](https://github.com/AMI-system/antenna/pull/1060)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#891](https://github.com/AMI-system/antenna/pull/891)(MERGED); [PR#645](https://github.com/AMI-system/antenna/pull/645)(MERGED); [PR#554](https://github.com/AMI-system/antenna/pull/554)(MERGED); [PR#306](https://github.com/AMI-system/antenna/pull/306)(MERGED); [PR#190](https://github.com/AMI-system/antenna/pull/190)(MERGED); [#1072](https://github.com/AMI-system/antenna/issues/1072)(CLOSED); [#963](https://github.com/AMI-system/antenna/issues/963)(CLOSED); [#874](https://github.com/AMI-system/antenna/issues/874)(CLOSED)_
- Script to fix date offsets — _[PR#809](https://github.com/AMI-system/antenna/pull/809)(MERGED); [PR#781](https://github.com/AMI-system/antenna/pull/781)(MERGED); [PR#1105](https://github.com/AMI-system/antenna/pull/1105)(MERGED); [PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED); [PR#778](https://github.com/AMI-system/antenna/pull/778)(MERGED); [PR#652](https://github.com/AMI-system/antenna/pull/652)(MERGED); [PR#1055](https://github.com/AMI-system/antenna/pull/1055)(MERGED); [PR#1048](https://github.com/AMI-system/antenna/pull/1048)(MERGED); [PR#905](https://github.com/AMI-system/antenna/pull/905)(MERGED); [PR#829](https://github.com/AMI-system/antenna/pull/829)(MERGED)_
- Deleting occurrences — _[PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [PR#250](https://github.com/AMI-system/antenna/pull/250)(MERGED); [#428](https://github.com/AMI-system/antenna/issues/428)(CLOSED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#608](https://github.com/AMI-system/antenna/pull/608)(MERGED); [#209](https://github.com/AMI-system/antenna/issues/209)(CLOSED); [#682](https://github.com/AMI-system/antenna/issues/682)(CLOSED); [PR#861](https://github.com/AMI-system/antenna/pull/861)(MERGED); [#865](https://github.com/AMI-system/antenna/issues/865)(OPEN)_
- Allow ability to delete deployments — _[PR#271](https://github.com/AMI-system/antenna/pull/271)(MERGED); [PR#331](https://github.com/AMI-system/antenna/pull/331)(MERGED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [#789](https://github.com/AMI-system/antenna/issues/789)(CLOSED); [#977](https://github.com/AMI-system/antenna/issues/977)(OPEN); [#413](https://github.com/AMI-system/antenna/issues/413)(OPEN); [#446](https://github.com/AMI-system/antenna/issues/446)(OPEN); [#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED); [PR#690](https://github.com/AMI-system/antenna/pull/690)(MERGED)_

### DevEx

- Multiple environments and auto deployment — _[#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED); [#196](https://github.com/AMI-system/antenna/issues/196)(CLOSED); [PR#1009](https://github.com/AMI-system/antenna/pull/1009)(MERGED); [#931](https://github.com/AMI-system/antenna/issues/931)(CLOSED)_

### Export/Interop

- Integration of final data into iNaturalist & GBIF — _[#217](https://github.com/AMI-system/antenna/issues/217)(CLOSED)_
- Integrate with iNaturalist for direct upload and validation of identified species — _[#217](https://github.com/AMI-system/antenna/issues/217)(CLOSED)_

### Infrastructure

- Data Uploader Tool (Desktop app to abstract S3 uploads / sync from SD cards) — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [PR#231](https://github.com/AMI-system/antenna/pull/231)(MERGED); [PR#76](https://github.com/AMI-system/antenna/pull/76)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED); [PR#146](https://github.com/AMI-system/antenna/pull/146)(MERGED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#593](https://github.com/AMI-system/antenna/issues/593)(OPEN); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED)_
- Automated backups (object storage backups) — _[#685](https://github.com/AMI-system/antenna/issues/685)(CLOSED)_
- Processing v2 & backend cleanup — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#1109](https://github.com/AMI-system/antenna/pull/1109)(MERGED); [PR#1125](https://github.com/AMI-system/antenna/pull/1125)(MERGED); [#1112](https://github.com/AMI-system/antenna/issues/1112)(OPEN); [PR#1113](https://github.com/AMI-system/antenna/pull/1113)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#1111](https://github.com/AMI-system/antenna/issues/1111)(OPEN); [#1085](https://github.com/AMI-system/antenna/issues/1085)(OPEN); [#1084](https://github.com/AMI-system/antenna/issues/1084)(CLOSED); [#515](https://github.com/AMI-system/antenna/issues/515)(OPEN)_
- Improving stability (implement processing v2) — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#1109](https://github.com/AMI-system/antenna/pull/1109)(MERGED); [PR#1113](https://github.com/AMI-system/antenna/pull/1113)(MERGED); [#1112](https://github.com/AMI-system/antenna/issues/1112)(OPEN); [PR#1125](https://github.com/AMI-system/antenna/pull/1125)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#1111](https://github.com/AMI-system/antenna/issues/1111)(OPEN); [#1085](https://github.com/AMI-system/antenna/issues/1085)(OPEN); [#1084](https://github.com/AMI-system/antenna/issues/1084)(CLOSED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN)_
- Develop a Data Uploader Tool (starting with CLI version) — _[#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#1061](https://github.com/AMI-system/antenna/issues/1061)(OPEN); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [#456](https://github.com/AMI-system/antenna/issues/456)(OPEN); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN)_
- Move UI kit back to Antenna repo (to reduce complexity) — _[PR#161](https://github.com/AMI-system/antenna/pull/161)(MERGED)_
- Scripts for sampling & uploading data — _[#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#1061](https://github.com/AMI-system/antenna/issues/1061)(OPEN); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [#456](https://github.com/AMI-system/antenna/issues/456)(OPEN); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN)_
- AMI Data Companion (for processing batch data offline) — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [PR#146](https://github.com/AMI-system/antenna/pull/146)(MERGED); [PR#266](https://github.com/AMI-system/antenna/pull/266)(MERGED); [#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [#676](https://github.com/AMI-system/antenna/issues/676)(CLOSED); [PR#688](https://github.com/AMI-system/antenna/pull/688)(MERGED); [PR#201](https://github.com/AMI-system/antenna/pull/201)(MERGED); [PR#79](https://github.com/AMI-system/antenna/pull/79)(MERGED)_
- Fix challenges with uploading large batches of images due to interface limitations — _[#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#1061](https://github.com/AMI-system/antenna/issues/1061)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [#456](https://github.com/AMI-system/antenna/issues/456)(OPEN); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED); [#904](https://github.com/AMI-system/antenna/issues/904)(OPEN); [PR#1062](https://github.com/AMI-system/antenna/pull/1062)(MERGED)_
- Increase file size limit for uploaded images — _[#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#1061](https://github.com/AMI-system/antenna/issues/1061)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [#456](https://github.com/AMI-system/antenna/issues/456)(OPEN); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN); [#904](https://github.com/AMI-system/antenna/issues/904)(OPEN)_
- Abstracting object store and allowing more uploading from UI and Desktop client — _[#640](https://github.com/AMI-system/antenna/issues/640)(CLOSED); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#1061](https://github.com/AMI-system/antenna/issues/1061)(OPEN); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [#455](https://github.com/AMI-system/antenna/issues/455)(OPEN); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED); [#1122](https://github.com/AMI-system/antenna/issues/1122)(OPEN); [#456](https://github.com/AMI-system/antenna/issues/456)(OPEN); [#904](https://github.com/AMI-system/antenna/issues/904)(OPEN)_
- Distributed data processing (hosting & serving models with multiple workers) — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#1109](https://github.com/AMI-system/antenna/pull/1109)(MERGED); [#1111](https://github.com/AMI-system/antenna/issues/1111)(OPEN); [#1112](https://github.com/AMI-system/antenna/issues/1112)(OPEN); [PR#1125](https://github.com/AMI-system/antenna/pull/1125)(MERGED); [PR#1113](https://github.com/AMI-system/antenna/pull/1113)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#1085](https://github.com/AMI-system/antenna/issues/1085)(OPEN); [#1084](https://github.com/AMI-system/antenna/issues/1084)(CLOSED); [#515](https://github.com/AMI-system/antenna/issues/515)(OPEN)_
- Processing v2: Move to a distributed task system — _[PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#1109](https://github.com/AMI-system/antenna/pull/1109)(MERGED); [#1084](https://github.com/AMI-system/antenna/issues/1084)(CLOSED); [#1112](https://github.com/AMI-system/antenna/issues/1112)(OPEN); [PR#1125](https://github.com/AMI-system/antenna/pull/1125)(MERGED); [PR#1113](https://github.com/AMI-system/antenna/pull/1113)(MERGED); [#1123](https://github.com/AMI-system/antenna/issues/1123)(OPEN); [#1111](https://github.com/AMI-system/antenna/issues/1111)(OPEN); [#1085](https://github.com/AMI-system/antenna/issues/1085)(OPEN); [#515](https://github.com/AMI-system/antenna/issues/515)(OPEN)_
- Data Uploader (easier data import/desktop application) — _[PR#292](https://github.com/AMI-system/antenna/pull/292)(MERGED); [PR#227](https://github.com/AMI-system/antenna/pull/227)(MERGED); [#259](https://github.com/AMI-system/antenna/issues/259)(CLOSED); [PR#838](https://github.com/AMI-system/antenna/pull/838)(MERGED); [PR#943](https://github.com/AMI-system/antenna/pull/943)(MERGED); [PR#281](https://github.com/AMI-system/antenna/pull/281)(MERGED); [#477](https://github.com/AMI-system/antenna/issues/477)(OPEN); [PR#987](https://github.com/AMI-system/antenna/pull/987)(MERGED); [PR#853](https://github.com/AMI-system/antenna/pull/853)(MERGED); [PR#522](https://github.com/AMI-system/antenna/pull/522)(MERGED)_

### ML/AI

- Generalized pipeline - General insect detector & Global moth classifier — _[PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [PR#484](https://github.com/AMI-system/antenna/pull/484)(OPEN)_
- Predict to order level only by default? — _[PR#712](https://github.com/AMI-system/antenna/pull/712)(MERGED); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)_
- Support for Costa Rica and Singapore regions/models — _[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED); [PR#917](https://github.com/AMI-system/antenna/pull/917)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#195](https://github.com/AMI-system/antenna/pull/195)(MERGED); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN)_
- Reprocessing of same objects — _[PR#719](https://github.com/AMI-system/antenna/pull/719)(MERGED); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [PR#718](https://github.com/AMI-system/antenna/pull/718)(CLOSED); [PR#706](https://github.com/AMI-system/antenna/pull/706)(CLOSED); [PR#1053](https://github.com/AMI-system/antenna/pull/1053)(MERGED); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#451](https://github.com/AMI-system/antenna/pull/451)(OPEN)_
- Clustering — _[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#832](https://github.com/AMI-system/antenna/pull/832)(OPEN); [#775](https://github.com/AMI-system/antenna/issues/775)(OPEN); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED); [PR#293](https://github.com/AMI-system/antenna/pull/293)(MERGED)_
- Cluster detections within the same family — _[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#1093](https://github.com/AMI-system/antenna/issues/1093)(OPEN); [PR#1045](https://github.com/AMI-system/antenna/pull/1045)(OPEN); [#992](https://github.com/AMI-system/antenna/issues/992)(OPEN); [PR#1091](https://github.com/AMI-system/antenna/pull/1091)(MERGED); [PR#1046](https://github.com/AMI-system/antenna/pull/1046)(MERGED); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED)_
- Post processing filters: Blurriness, darkness, brightness (evaluating the image quality) — _[PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [PR#954](https://github.com/AMI-system/antenna/pull/954)(MERGED); [PR#890](https://github.com/AMI-system/antenna/pull/890)(OPEN); [PR#957](https://github.com/AMI-system/antenna/pull/957)(CLOSED)_
- Class masking & global model - then generate rank classifications as additional classifications — _[PR#573](https://github.com/AMI-system/antenna/pull/573)(MERGED); [PR#999](https://github.com/AMI-system/antenna/pull/999)(OPEN); [#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#915](https://github.com/AMI-system/antenna/issues/915)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)_
- Missing Not Identifiable class in OOD environment — _[PR#842](https://github.com/AMI-system/antenna/pull/842)(MERGED); [#811](https://github.com/AMI-system/antenna/issues/811)(CLOSED); [PR#888](https://github.com/AMI-system/antenna/pull/888)(MERGED); [PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#984](https://github.com/AMI-system/antenna/pull/984)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED)_
- Many to many, storing feature embedding, etc. — _[PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#807](https://github.com/AMI-system/antenna/pull/807)(MERGED); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED); [PR#1050](https://github.com/AMI-system/antenna/pull/1050)(OPEN); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#670](https://github.com/AMI-system/antenna/pull/670)(MERGED); [#875](https://github.com/AMI-system/antenna/issues/875)(OPEN); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#816](https://github.com/AMI-system/antenna/pull/816)(OPEN); [PR#707](https://github.com/AMI-system/antenna/pull/707)(OPEN)_
- Continue to maintain and enhance automated detection and classification — _[PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [#628](https://github.com/AMI-system/antenna/issues/628)(CLOSED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED); [#220](https://github.com/AMI-system/antenna/issues/220)(CLOSED)_
- Clustering for labeling (vector search backend) — _[PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [#846](https://github.com/AMI-system/antenna/issues/846)(CLOSED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#827](https://github.com/AMI-system/antenna/issues/827)(CLOSED); [PR#859](https://github.com/AMI-system/antenna/pull/859)(MERGED); [PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED); [PR#845](https://github.com/AMI-system/antenna/pull/845)(OPEN); [PR#832](https://github.com/AMI-system/antenna/pull/832)(OPEN); [#775](https://github.com/AMI-system/antenna/issues/775)(OPEN); [PR#185](https://github.com/AMI-system/antenna/pull/185)(MERGED)_

### Permissions/Auth

- Feature: Configure members for a project is partially implemented — _[PR#1004](https://github.com/AMI-system/antenna/pull/1004)(MERGED)_
- Private vs. Public projects. Fix permission boundaries. — _[PR#277](https://github.com/AMI-system/antenna/pull/277)(MERGED)_
- Setting some projects to drafts — _[PR#1012](https://github.com/AMI-system/antenna/pull/1012)(MERGED); [PR#1004](https://github.com/AMI-system/antenna/pull/1004)(MERGED)_
- Roles (Not only a permissions feature but a way to organize and simplify the interface for different types of users) — _[PR#277](https://github.com/AMI-system/antenna/pull/277)(MERGED)_
- Add is_staff to each user — _[PR#235](https://github.com/AMI-system/antenna/pull/235)(MERGED); [PR#449](https://github.com/AMI-system/antenna/pull/449)(MERGED)_
- Project & Team Management (UI & API for managing user roles) — _[PR#727](https://github.com/AMI-system/antenna/pull/727)(CLOSED)_
- Unstable Functions (password reset/sign-up disabled) — _[PR#526](https://github.com/AMI-system/antenna/pull/526)(MERGED)_

### Research

- LoRAs for regional models — _[PR#962](https://github.com/AMI-system/antenna/pull/962)(MERGED); [#469](https://github.com/AMI-system/antenna/issues/469)(OPEN); [#517](https://github.com/AMI-system/antenna/issues/517)(CLOSED); [PR#608](https://github.com/AMI-system/antenna/pull/608)(MERGED); [PR#453](https://github.com/AMI-system/antenna/pull/453)(MERGED); [PR#630](https://github.com/AMI-system/antenna/pull/630)(OPEN); [#412](https://github.com/AMI-system/antenna/issues/412)(OPEN); [#272](https://github.com/AMI-system/antenna/issues/272)(OPEN)_
- What steps can we take to improve the classifiers over the coming years? — _[PR#613](https://github.com/AMI-system/antenna/pull/613)(MERGED); [PR#574](https://github.com/AMI-system/antenna/pull/574)(MERGED); [PR#607](https://github.com/AMI-system/antenna/pull/607)(CLOSED); [#952](https://github.com/AMI-system/antenna/issues/952)(OPEN); [#857](https://github.com/AMI-system/antenna/issues/857)(OPEN); [PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#821](https://github.com/AMI-system/antenna/pull/821)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED)_
- Concern about accuracy of species detection/classification — _[PR#815](https://github.com/AMI-system/antenna/pull/815)(MERGED); [#628](https://github.com/AMI-system/antenna/issues/628)(CLOSED); [PR#837](https://github.com/AMI-system/antenna/pull/837)(MERGED); [PR#818](https://github.com/AMI-system/antenna/pull/818)(MERGED); [PR#814](https://github.com/AMI-system/antenna/pull/814)(MERGED); [PR#798](https://github.com/AMI-system/antenna/pull/798)(MERGED); [PR#374](https://github.com/AMI-system/antenna/pull/374)(MERGED); [#774](https://github.com/AMI-system/antenna/issues/774)(CLOSED); [#752](https://github.com/AMI-system/antenna/issues/752)(CLOSED); [#220](https://github.com/AMI-system/antenna/issues/220)(CLOSED)_

### Taxonomy

- Features for grouping & filtering species lists — _[PR#850](https://github.com/AMI-system/antenna/pull/850)(MERGED)_
- Importing for Taxonomy (bulk import to assign to lists) — _[#622](https://github.com/AMI-system/antenna/issues/622)(CLOSED)_

### UI/UX

- Misc. UI gaps: More obvious interlinking between occurrence and session detail — _[#651](https://github.com/AMI-system/antenna/issues/651)(CLOSED); [PR#794](https://github.com/AMI-system/antenna/pull/794)(MERGED); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED); [#443](https://github.com/AMI-system/antenna/issues/443)(CLOSED); [PR#692](https://github.com/AMI-system/antenna/pull/692)(MERGED)_
- Hovering toolbar in the session detail per occurrence? — _[#651](https://github.com/AMI-system/antenna/issues/651)(CLOSED); [PR#794](https://github.com/AMI-system/antenna/pull/794)(MERGED); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED); [#443](https://github.com/AMI-system/antenna/issues/443)(CLOSED); [#585](https://github.com/AMI-system/antenna/issues/585)(CLOSED)_
- Size filter — _[PR#1031](https://github.com/AMI-system/antenna/pull/1031)(MERGED)_
- Link to filter taxa by parent (from taxa detail view)? — _[PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#578](https://github.com/AMI-system/antenna/pull/578)(MERGED); [PR#830](https://github.com/AMI-system/antenna/pull/830)(MERGED)_
- Add verification features to gallery view — _[PR#785](https://github.com/AMI-system/antenna/pull/785)(MERGED); [PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#643](https://github.com/AMI-system/antenna/pull/643)(MERGED)_
- Make taxa detail page — _[#485](https://github.com/AMI-system/antenna/issues/485)(CLOSED)_
- Fix incorrect date display for all occurrences — _[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED)_
- Knowing what's been processed (images uploaded/in a project/collection) — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED); [#680](https://github.com/AMI-system/antenna/issues/680)(CLOSED)_
- Knowing what's been verified (progress bar reflection) — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED)_
- Bulk agree option for annotation — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#460](https://github.com/AMI-system/antenna/pull/460)(MERGED)_
- UI for faster verification — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#785](https://github.com/AMI-system/antenna/pull/785)(MERGED); [PR#460](https://github.com/AMI-system/antenna/pull/460)(MERGED)_
- Automatically hide vetted items as user proceeds — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED)_
- Filtering by species/genus/taco level with children levels (already in place) — _[PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#830](https://github.com/AMI-system/antenna/pull/830)(MERGED)_
- Determine where users can type in a species name for search/filtering — _[PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#830](https://github.com/AMI-system/antenna/pull/830)(MERGED); [PR#578](https://github.com/AMI-system/antenna/pull/578)(MERGED)_
- Ability to validate both low-confidence and high-confidence predictions — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED)_
- Display multiple labels in a suggest ID section for re-identification — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#460](https://github.com/AMI-system/antenna/pull/460)(MERGED)_
- Collaborative identification or validation — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#785](https://github.com/AMI-system/antenna/pull/785)(MERGED); [PR#460](https://github.com/AMI-system/antenna/pull/460)(MERGED)_
- Ability to share links to occurrences sessions or summaries — _[PR#794](https://github.com/AMI-system/antenna/pull/794)(MERGED); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED); [#651](https://github.com/AMI-system/antenna/issues/651)(CLOSED); [#443](https://github.com/AMI-system/antenna/issues/443)(CLOSED)_
- Filtering based on model used (session view occurrence view) — _[PR#185](https://github.com/AMI-system/antenna/pull/185)(MERGED); [PR#794](https://github.com/AMI-system/antenna/pull/794)(MERGED); [#443](https://github.com/AMI-system/antenna/issues/443)(CLOSED); [#791](https://github.com/AMI-system/antenna/issues/791)(CLOSED); [#651](https://github.com/AMI-system/antenna/issues/651)(CLOSED)_
- Selection of device site etc. in Deployment — _[PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED)_
- Identification view (Supports multiple users keeps track of history allows for bulk ID or ID to coarser labels) — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#460](https://github.com/AMI-system/antenna/pull/460)(MERGED)_
- Ability to share URLs (Deep links to single session captures or directions from a specific taxon group) — _[PR#195](https://github.com/AMI-system/antenna/pull/195)(MERGED)_
- Expose more features for user to manage species list and view charts (MVP for March) — _[PR#580](https://github.com/AMI-system/antenna/pull/580)(MERGED); [PR#577](https://github.com/AMI-system/antenna/pull/577)(MERGED)_
- New filter: Show occurrences where there is any disagreement (between models or humans) — _[PR#840](https://github.com/AMI-system/antenna/pull/840)(MERGED)_
- See what captures has been processed and not (Missing data about this) — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- Add new frontend views like "My projects" and show multiple suggestions per classification — _[PR#741](https://github.com/AMI-system/antenna/pull/741)(MERGED)_
- Filter for confidence in Taxa view — _[PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#578](https://github.com/AMI-system/antenna/pull/578)(MERGED); [PR#830](https://github.com/AMI-system/antenna/pull/830)(MERGED)_
- Show the Site & Device as columns in Station list view — _[PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED)_
- Update filter of taxa best confidence to allow None (filter out unobserved species with score of None) — _[PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED)_
- Put cursor in taxon search field after clicking the magnifying glass — _[PR#951](https://github.com/AMI-system/antenna/pull/951)(MERGED); [PR#856](https://github.com/AMI-system/antenna/pull/856)(MERGED); [PR#851](https://github.com/AMI-system/antenna/pull/851)(MERGED); [PR#255](https://github.com/AMI-system/antenna/pull/255)(MERGED)_
- Interactive tool to manually annotate or correct detections — _[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED)_
- Fix lack of specific field validation errors when creating deployment — _[#400](https://github.com/AMI-system/antenna/issues/400)(CLOSED)_
- Fix difficulty in saving deployment without changing a field — _[PR#1074](https://github.com/AMI-system/antenna/pull/1074)(MERGED)_
- Show all detections regardless of score threshold — _[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED)_
- Fix missing user name in detail view of identification history — _[PR#841](https://github.com/AMI-system/antenna/pull/841)(MERGED); [PR#785](https://github.com/AMI-system/antenna/pull/785)(MERGED)_
- Use clearer link text for viewing source image — _[PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [PR#1031](https://github.com/AMI-system/antenna/pull/1031)(MERGED)_
- Uncertainty about expected image upload count — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- Implement auto-refresh after processing single image — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED); [#901](https://github.com/AMI-system/antenna/issues/901)(CLOSED)_
- Continue to maintain clear indication of image upload status — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- Clarify header image upload during deployment creation — _[#789](https://github.com/AMI-system/antenna/issues/789)(CLOSED); [#314](https://github.com/AMI-system/antenna/issues/314)(CLOSED)_
- Continue to maintain the manual upload feature for images — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- Manually edit bounding box annotations for detections — _[PR#214](https://github.com/AMI-system/antenna/pull/214)(MERGED); [PR#126](https://github.com/AMI-system/antenna/pull/126)(MERGED)_
- Post processing UI — _[PR#849](https://github.com/AMI-system/antenna/pull/849)(MERGED)_
- Cover image fields — _[PR#300](https://github.com/AMI-system/antenna/pull/300)(MERGED); [PR#187](https://github.com/AMI-system/antenna/pull/187)(MERGED); [PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED)_
- Separate image uploading from first two steps during deployment registration — _[#789](https://github.com/AMI-system/antenna/issues/789)(CLOSED)_
- Being able to click the save after uploading sample capture images — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- Add deployment count column to Device Types list — _[PR#333](https://github.com/AMI-system/antenna/pull/333)(MERGED)_
- Knowing What's Processed (progress bar/how many images processed) — _[PR#961](https://github.com/AMI-system/antenna/pull/961)(MERGED)_
- UI Gaps/Fixes (consistent saving/quick buttons/show best detection image) — _[PR#1058](https://github.com/AMI-system/antenna/pull/1058)(MERGED)_

</details>

---

## Out of Scope (16 items)

_Field protocol notes, action items for specific people, and hardware decisions. Not software features._

- Better db snapshots for automated and manual testing
- Michael onboarded Tessa to the data companion code and she has committed several enhancements
- Label each SD card with tape them and label them
- Make sure the SD card is identify to see from which camera it came from
- Sync the SD cards every day to hardware 1 & 2
- Sync to the cloud (Anna)
- Fresh SD cards
- Assign it the night before who will be doing it (Demo)
- Needs to be put in a boxe
- Wipe them
- Rename the files (Anna)
- Sample the files (Anna)
- 10 minutes intervals (Sampling)
- Charge batteries
- Daily morning SD cards collection of the entocam
- Reinstall them
