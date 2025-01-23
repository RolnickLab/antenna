export enum STRING {
  /* BUTTON */
  AGREE,
  AGREED,
  BACK,
  CANCEL,
  CHANGE_IMAGE,
  CHOOSE_IMAGE,
  CLEAR,
  CLEAR_FILTERS,
  COLLAPSE,
  CURRENT_LOCATION,
  DELETE,
  DELETED,
  EDIT,
  EXPAND,
  LOGIN,
  LOGOUT,
  NEXT,
  PROCESS_NOW,
  POPULATE,
  QUEUED,
  REFRESH,
  RESET,
  RETRY,
  RERUN,
  SAVE,
  SAVED,
  SEARCH_MAP,
  SEND_INSTRUCTIONS,
  SIGN_UP,
  STAR,
  STARRED,
  START,
  SUBMIT,
  SUGGEST_ID,
  SUGGEST_ID_SHORT,
  SYNC,
  TEST,
  TEST_CONNECTION,
  VIEW_PUBLIC_PROJECTS,

  /* ENTITY */
  ENTITY_CREATE,
  ENTITY_DELETE,
  ENTITY_DETAILS,
  ENTITY_EDIT,
  ENTITY_TYPE_CAPTURE,
  ENTITY_TYPE_DEPLOYMENT,
  ENTITY_TYPE_IDENTIFICATION,
  ENTITY_TYPE_PIPELINE,
  ENTITY_TYPE_JOB,
  ENTITY_TYPE_PROJECT,
  ENTITY_VIEW,

  /* FIELD_LABEL */
  FIELD_LABEL_AVG_TEMP,
  FIELD_LABEL_BEST_SCORE,
  FIELD_LABEL_CAPTURES,
  FIELD_LABEL_CAPTURES_WITH_DETECTIONS,
  FIELD_LABEL_COMMENT,
  FIELD_LABEL_CONNECTION_STATUS,
  FIELD_LABEL_CREATED_AT,
  FIELD_LABEL_DATA_SOURCE_CAPTURES,
  FIELD_LABEL_DATE,
  FIELD_LABEL_DATE_OBSERVED,
  FIELD_LABEL_DELAY,
  FIELD_LABEL_DEPLOYMENT,
  FIELD_LABEL_DESCRIPTION,
  FIELD_LABEL_DEVICE,
  FIELD_LABEL_DURATION,
  FIELD_LABEL_EMAIL,
  FIELD_LABEL_EMAIL_NEW,
  FIELD_LABEL_ERRORS,
  FIELD_LABEL_FINISHED_AT,
  FIELD_LABEL_GENERAL,
  FIELD_LABEL_ID,
  FIELD_LABEL_IMAGE,
  FIELD_LABEL_ICON,
  FIELD_LABEL_JOBS,
  FIELD_LABEL_LAST_SYNCED,
  FIELD_LABEL_LATITUDE,
  FIELD_LABEL_LOCATION,
  FIELD_LABEL_LOGS,
  FIELD_LABEL_LONGITUDE,
  FIELD_LABEL_MOST_RECENT,
  FIELD_LABEL_NAME,
  FIELD_LABEL_NEW_PASSWORD,
  FIELD_LABEL_OCCURRENCES,
  FIELD_LABEL_PASSWORD,
  FIELD_LABEL_PASSWORD_CURRENT,
  FIELD_LABEL_PASSWORD_NEW,
  FIELD_LABEL_PATH,
  FIELD_LABEL_PIPELINE,
  FIELD_LABEL_PROCESS,
  FIELD_LABEL_PROJECT,
  FIELD_LABEL_SAMPLING_METHOD,
  FIELD_LABEL_SESSION,
  FIELD_LABEL_SESSIONS,
  FIELD_LABEL_SITE,
  FIELD_LABEL_SIZE,
  FIELD_LABEL_SOURCE_IMAGE,
  FIELD_LABEL_SOURCE_IMAGES,
  FIELD_LABEL_DATA_SOURCE,
  FIELD_LABEL_SAMPLE_CAPTURES,
  FIELD_LABEL_SCORE,
  FIELD_LABEL_SCORE_THRESHOLD,
  FIELD_LABEL_SNAPSHOTS,
  FIELD_LABEL_STARTED_AT,
  FIELD_LABEL_STATUS,
  FIELD_LABEL_TAXON,
  FIELD_LABEL_TAXA,
  FIELD_LABEL_THUMBNAIL,
  FIELD_LABEL_TIME,
  FIELD_LABEL_TIME_OBSERVED,
  FIELD_LABEL_TIMESTAMP,
  FIELD_LABEL_TOTAL_FILES,
  FIELD_LABEL_TOTAL_SIZE,
  FIELD_LABEL_TRAINING_IMAGES,
  FIELD_LABEL_TYPE,
  FIELD_LABEL_FIRST_DATE,
  FIELD_LABEL_LAST_DATE,
  FIELD_LABEL_UPDATED_AT,
  FIELD_LABEL_UPLOAD_CAPTURES,
  FIELD_LABEL_VERSION,
  FIELD_LABEL_VERSION_NAME,

  /* MESSAGE */
  MESSAGE_CAPTURE_FILENAME,
  MESSAGE_CAPTURE_LIMIT,
  MESSAGE_CAPTURE_SYNC_HIDDEN,
  MESSAGE_CAPTURE_TOO_MANY,
  MESSAGE_CAPTURE_UPLOAD_HIDDEN,
  MESSAGE_CHANGE_PASSWORD,
  MESSAGE_COULD_NOT_SAVE,
  MESSAGE_DATA_SOURCE_NOT_CONFIGURED,
  MESSAGE_DELETE_CONFIRM,
  MESSAGE_HAS_ACCOUNT,
  MESSAGE_IMAGE_FORMAT,
  MESSAGE_IMAGE_SIZE,
  MESSAGE_IMAGE_TOO_BIG,
  MESSAGE_NO_ACCOUNT_YET,
  MESSAGE_NO_IMAGE,
  MESSAGE_NO_RESULTS,
  MESSAGE_NO_RESULTS_FOR_FILTERING,
  MESSAGE_PASSWORD_FORMAT,
  MESSAGE_PASSWORD_UPDATED,
  MESSAGE_PERMISSIONS_MISSING,
  MESSAGE_PROCESS_NOW_TOOLTIP,
  MESSAGE_RESET_INSTRUCTIONS_SENT,
  MESSAGE_RESULT_RANGE,
  MESSAGE_SIGNED_UP,
  MESSAGE_VALUE_INVALID,
  MESSAGE_VALUE_MISSING,

  /* NAV_ITEM */
  NAV_ITEM_DEPLOYMENTS,
  NAV_ITEM_JOBS,
  NAV_ITEM_OCCURRENCES,
  NAV_ITEM_OVERVIEW,
  NAV_ITEM_PROJECTS,
  NAV_ITEM_SESSIONS,
  NAV_ITEM_TAXA,

  /* TAB_ITEM */
  TAB_ITEM_ALL_PROJECTS,
  TAB_ITEM_COLLECTIONS,
  TAB_ITEM_DEVICES,
  TAB_ITEM_FIELDS,
  TAB_ITEM_GALLERY,
  TAB_ITEM_IDENTIFICATION,
  TAB_ITEM_MY_PROJECTS,
  TAB_ITEM_PIPELINES,
  TAB_ITEM_SITES,
  TAB_ITEM_STORAGE,
  TAB_ITEM_SUMMARY,
  TAB_ITEM_TABLE,

  /* JOB STATUS */
  CREATED,
  PENDING,
  RUNNING,
  CANCELING,
  REVOKED,
  FAILED,
  DONE,

  /* TOOLTIPS */
  TOOLTIP_COLLECTION,
  TOOLTIP_DEPLOYMENT,
  TOOLTIP_DEVICE_TYPE,
  TOOLTIP_JOB,
  TOOLTIP_OCCURRENCE,
  TOOLTIP_PIPELINE,
  TOOLTIP_SESSION,
  TOOLTIP_SITE,
  TOOLTIP_STATUS,
  TOOLTIP_STORAGE,

  /* OTHER */
  ALGORITHMS,
  APPLY_ID,
  APPLY_ID_SHORT,
  BACK_TO_LOGIN,
  CLOSE,
  COLUMNS,
  CONNECTED,
  CONNECTING,
  FORGOT_PASSWORD,
  FORGOT_PASSWORD_DETAILS,
  ID_APPLIED,
  LAST_UPDATED,
  LOADING_DATA,
  MACHINE_PREDICTION_SCORE,
  MACHINE_SUGGESTION,
  NEW_ID,
  NOT_CONNECTED,
  OR,
  RECENT,
  REJECT_ID,
  REJECT_ID_SHORT,
  SELECT_COLUMNS,
  RESULTS,
  SET_PASSWORD,
  SET_PASSWORD_DETAILS,
  STAGES,
  SUMMARY,
  UNKNOWN,
  UNKNOWN_ERROR,
  UPDATING_DATA,
  USER_INFO,
  VERIFIED_BY,
  VALUE_NOT_AVAILABLE,
}

const ENGLISH_STRINGS: { [key in STRING]: string } = {
  /* BUTTON */
  [STRING.AGREE]: 'Agree',
  [STRING.AGREED]: 'Agreed',
  [STRING.BACK]: 'Back',
  [STRING.CANCEL]: 'Cancel',
  [STRING.CHANGE_IMAGE]: 'Change image',
  [STRING.CHOOSE_IMAGE]: 'Choose image',
  [STRING.CLEAR]: 'Clear',
  [STRING.CLEAR_FILTERS]: 'Clear filters',
  [STRING.COLLAPSE]: 'Collapse',
  [STRING.CURRENT_LOCATION]: 'Use current location',
  [STRING.DELETE]: 'Delete',
  [STRING.DELETED]: 'Deleted',
  [STRING.EDIT]: 'Edit',
  [STRING.EXPAND]: 'Expand',
  [STRING.LOGIN]: 'Login',
  [STRING.LOGOUT]: 'Logout',
  [STRING.NEXT]: 'Next',
  [STRING.PROCESS_NOW]: 'Process now',
  [STRING.POPULATE]: 'Populate',
  [STRING.QUEUED]: 'Queued',
  [STRING.REFRESH]: 'Refresh',
  [STRING.RESET]: 'Reset',
  [STRING.RETRY]: 'Retry',
  [STRING.RERUN]: 'Re-run',
  [STRING.SAVE]: 'Save',
  [STRING.SAVED]: 'Saved',
  [STRING.SEARCH_MAP]: 'Search on the map',
  [STRING.SEND_INSTRUCTIONS]: 'Send instructions',
  [STRING.SIGN_UP]: 'Sign up',
  [STRING.STAR]: 'Add to starred collection',
  [STRING.STARRED]: 'Remove from starred collection',
  [STRING.START]: 'Start',
  [STRING.SUBMIT]: 'Submit',
  [STRING.SUGGEST_ID]: 'Suggest ID',
  [STRING.SUGGEST_ID_SHORT]: 'Suggest',
  [STRING.SYNC]: 'Sync',
  [STRING.TEST]: 'Test',
  [STRING.TEST_CONNECTION]: 'Test Connection',
  [STRING.VIEW_PUBLIC_PROJECTS]: 'View public projects',

  /* FIELD_LABEL */
  [STRING.FIELD_LABEL_AVG_TEMP]: 'Avg temp',
  [STRING.FIELD_LABEL_BEST_SCORE]: 'Best score',
  [STRING.FIELD_LABEL_CAPTURES]: 'Captures',
  [STRING.FIELD_LABEL_CAPTURES_WITH_DETECTIONS]: 'Captures w/detections',
  [STRING.FIELD_LABEL_COMMENT]: 'Comment',
  [STRING.FIELD_LABEL_CONNECTION_STATUS]: 'Connection status',
  [STRING.FIELD_LABEL_CREATED_AT]: 'Created at',
  [STRING.FIELD_LABEL_DATA_SOURCE_CAPTURES]: 'Data source captures',
  [STRING.FIELD_LABEL_DATE]: 'Date',
  [STRING.FIELD_LABEL_DATE_OBSERVED]: 'Date observed',
  [STRING.FIELD_LABEL_DELAY]: 'Delay',
  [STRING.FIELD_LABEL_DEVICE]: 'Device type',
  [STRING.FIELD_LABEL_DEPLOYMENT]: 'Station',
  [STRING.FIELD_LABEL_DESCRIPTION]: 'Description',
  [STRING.FIELD_LABEL_DURATION]: 'Duration',
  [STRING.FIELD_LABEL_EMAIL]: 'Email',
  [STRING.FIELD_LABEL_EMAIL_NEW]: 'Email new',
  [STRING.FIELD_LABEL_ERRORS]: 'Errors',
  [STRING.FIELD_LABEL_FINISHED_AT]: 'Finished at',
  [STRING.FIELD_LABEL_GENERAL]: 'General configuration',
  [STRING.FIELD_LABEL_ID]: 'ID',
  [STRING.FIELD_LABEL_IMAGE]: 'Cover image',
  [STRING.FIELD_LABEL_ICON]: 'Icon',
  [STRING.FIELD_LABEL_JOBS]: 'Jobs',
  [STRING.FIELD_LABEL_LAST_SYNCED]: 'Last synced with data source',
  [STRING.FIELD_LABEL_LATITUDE]: 'Latitude',
  [STRING.FIELD_LABEL_LOCATION]: 'Location',
  [STRING.FIELD_LABEL_LOGS]: 'Logs',
  [STRING.FIELD_LABEL_LONGITUDE]: 'Longitude',
  [STRING.FIELD_LABEL_MOST_RECENT]: 'Most recent',
  [STRING.FIELD_LABEL_NAME]: 'Name',
  [STRING.FIELD_LABEL_NEW_PASSWORD]: 'New password',
  [STRING.FIELD_LABEL_OCCURRENCES]: 'Occurrences',
  [STRING.FIELD_LABEL_PASSWORD]: 'Password',
  [STRING.FIELD_LABEL_PASSWORD_CURRENT]: 'Current password',
  [STRING.FIELD_LABEL_PASSWORD_NEW]: 'New password',
  [STRING.FIELD_LABEL_PATH]: 'Path',
  [STRING.FIELD_LABEL_PIPELINE]: 'Pipeline',
  [STRING.FIELD_LABEL_PROCESS]: 'Process',
  [STRING.FIELD_LABEL_PROJECT]: 'Project',
  [STRING.FIELD_LABEL_SAMPLING_METHOD]: 'Sampling method',
  [STRING.FIELD_LABEL_SESSION]: 'Session',
  [STRING.FIELD_LABEL_SESSIONS]: 'Sessions',
  [STRING.FIELD_LABEL_SITE]: 'Site',
  [STRING.FIELD_LABEL_SIZE]: 'Size',
  [STRING.FIELD_LABEL_SOURCE_IMAGE]: 'Source image',
  [STRING.FIELD_LABEL_SOURCE_IMAGES]: 'Source image collection',
  [STRING.FIELD_LABEL_DATA_SOURCE]: 'Data source',
  [STRING.FIELD_LABEL_SAMPLE_CAPTURES]: 'Sample images',
  [STRING.FIELD_LABEL_SCORE]: 'Score',
  [STRING.FIELD_LABEL_SCORE_THRESHOLD]: 'Score threshold',
  [STRING.FIELD_LABEL_SNAPSHOTS]: 'Snapshots',
  [STRING.FIELD_LABEL_STARTED_AT]: 'Started at',
  [STRING.FIELD_LABEL_STATUS]: 'Status',
  [STRING.FIELD_LABEL_TAXA]: 'Taxa',
  [STRING.FIELD_LABEL_TAXON]: 'Taxon',
  [STRING.FIELD_LABEL_THUMBNAIL]: 'Thumbnail',
  [STRING.FIELD_LABEL_TIME]: 'Local time',
  [STRING.FIELD_LABEL_TIME_OBSERVED]: 'Local time observed',
  [STRING.FIELD_LABEL_TIMESTAMP]: 'Timestamp',
  [STRING.FIELD_LABEL_TOTAL_FILES]: 'Total files',
  [STRING.FIELD_LABEL_TOTAL_SIZE]: 'Total size',
  [STRING.FIELD_LABEL_TRAINING_IMAGES]: 'Reference images',
  [STRING.FIELD_LABEL_TYPE]: 'Type',
  [STRING.FIELD_LABEL_FIRST_DATE]: 'First date',
  [STRING.FIELD_LABEL_LAST_DATE]: 'Last date',
  [STRING.FIELD_LABEL_UPLOAD_CAPTURES]: 'Upload images',
  [STRING.FIELD_LABEL_UPDATED_AT]: 'Updated at',
  [STRING.FIELD_LABEL_VERSION]: 'Version',
  [STRING.FIELD_LABEL_VERSION_NAME]: 'Version',

  /* ENTITY */
  [STRING.ENTITY_CREATE]: 'Register new {{type}}',
  [STRING.ENTITY_DELETE]: 'Delete {{type}}',
  [STRING.ENTITY_DETAILS]: '{{type}} details',
  [STRING.ENTITY_EDIT]: 'Edit {{type}}',
  [STRING.ENTITY_TYPE_CAPTURE]: 'capture',
  [STRING.ENTITY_TYPE_DEPLOYMENT]: 'station',
  [STRING.ENTITY_TYPE_IDENTIFICATION]: 'identification',
  [STRING.ENTITY_TYPE_PIPELINE]: 'pipeline',
  [STRING.ENTITY_TYPE_JOB]: 'job',
  [STRING.ENTITY_TYPE_PROJECT]: 'project',
  [STRING.ENTITY_VIEW]: 'View {{type}}',

  /* MESSAGE */
  [STRING.MESSAGE_CAPTURE_FILENAME]:
    'Image filename must contain a timestamp in the format YYYYMMDDHHMMSS (e.g. 20210101120000-snapshot.jpg).',
  [STRING.MESSAGE_CAPTURE_LIMIT]:
    'A maximum of {{numCaptures}} images can be uploaded through the web browser. Configure a data source to upload data in bulk.',
  [STRING.MESSAGE_CAPTURE_SYNC_HIDDEN]:
    'Station must be created before syncing images.',
  [STRING.MESSAGE_CAPTURE_TOO_MANY]:
    'To upload more than {{numCaptures}} images you must configure a data source.',
  [STRING.MESSAGE_CAPTURE_UPLOAD_HIDDEN]:
    'Station must be created before uploading images.',
  [STRING.MESSAGE_CHANGE_PASSWORD]:
    'Contact an administrator to change your email or password.',
  [STRING.MESSAGE_COULD_NOT_SAVE]: 'Could not save',
  [STRING.MESSAGE_DATA_SOURCE_NOT_CONFIGURED]:
    'A data source must be configured and saved before syncing images.',
  [STRING.MESSAGE_DELETE_CONFIRM]:
    'Are you sure you want to delete this {{type}}?',
  [STRING.MESSAGE_HAS_ACCOUNT]: 'Already have an account?',
  [STRING.MESSAGE_IMAGE_FORMAT]: 'Valid formats are PNG, GIF and JPEG.',
  [STRING.MESSAGE_IMAGE_SIZE]:
    'The image must smaller than {{value}} {{unit}}.',
  [STRING.MESSAGE_IMAGE_TOO_BIG]: 'Please provide a smaller image',
  [STRING.MESSAGE_NO_ACCOUNT_YET]: 'No account yet?',
  [STRING.MESSAGE_NO_IMAGE]: 'No image',
  [STRING.MESSAGE_NO_RESULTS]: 'No results to show.',
  [STRING.MESSAGE_NO_RESULTS_FOR_FILTERING]:
    'No results to show for the current fitering.',
  [STRING.MESSAGE_PASSWORD_FORMAT]:
    'The password must contain at least 8 characters and cannot be entirely numeric.',
  [STRING.MESSAGE_PASSWORD_UPDATED]: 'Your password has been updated!',
  [STRING.MESSAGE_PERMISSIONS_MISSING]:
    'Permissions missing to perform the action',
  [STRING.MESSAGE_PROCESS_NOW_TOOLTIP]:
    'Process this single image with presets',
  [STRING.MESSAGE_RESET_INSTRUCTIONS_SENT]:
    'Reset intructions has been sent to {{email}}!',
  [STRING.MESSAGE_RESULT_RANGE]:
    'Showing {{start}}-{{end}} of {{total}} result(s)',
  [STRING.MESSAGE_SIGNED_UP]: 'Signed up successfully!',
  [STRING.MESSAGE_VALUE_INVALID]: 'Please provide a valid value',
  [STRING.MESSAGE_VALUE_MISSING]: 'Please provide a value',

  /* NAV_ITEM */
  [STRING.NAV_ITEM_DEPLOYMENTS]: 'Stations',
  [STRING.NAV_ITEM_JOBS]: 'Jobs',
  [STRING.NAV_ITEM_OCCURRENCES]: 'Occurrences',
  [STRING.NAV_ITEM_OVERVIEW]: 'Overview',
  [STRING.NAV_ITEM_PROJECTS]: 'Projects',
  [STRING.NAV_ITEM_SESSIONS]: 'Sessions',
  [STRING.NAV_ITEM_TAXA]: 'Taxa',

  /* TAB_ITEM */
  [STRING.TAB_ITEM_ALL_PROJECTS]: 'All projects',
  [STRING.TAB_ITEM_COLLECTIONS]: 'Collections',
  [STRING.TAB_ITEM_DEVICES]: 'Device types',
  [STRING.TAB_ITEM_FIELDS]: 'Fields',
  [STRING.TAB_ITEM_GALLERY]: 'Gallery view',
  [STRING.TAB_ITEM_IDENTIFICATION]: 'Identification',
  [STRING.TAB_ITEM_MY_PROJECTS]: 'My projects',
  [STRING.TAB_ITEM_PIPELINES]: 'Pipelines',
  [STRING.TAB_ITEM_SITES]: 'Sites',
  [STRING.TAB_ITEM_STORAGE]: 'Storage',
  [STRING.TAB_ITEM_SUMMARY]: 'Summary',
  [STRING.TAB_ITEM_TABLE]: 'Table view',

  /* JOB STATUS */
  [STRING.CREATED]: 'Created',
  [STRING.PENDING]: 'Pending',
  [STRING.RUNNING]: 'Running',
  [STRING.CANCELING]: 'Canceling',
  [STRING.REVOKED]: 'Canceled',
  [STRING.FAILED]: 'Failed',
  [STRING.DONE]: 'Done',

  /* TOOLTIPS */
  [STRING.TOOLTIP_COLLECTION]:
    'A collection is a group of source images. A collection contains all or some images in a project. When a processing job is registered, a collection is picked. This list defines the collection options available.',
  [STRING.TOOLTIP_DEPLOYMENT]:
    'A monitoring station is a location where a device is deployed to take images of insects in the wild (at a “Site”).',
  [STRING.TOOLTIP_DEVICE_TYPE]:
    'A device type is the type of equipment or camera used for collecting source images. One or many deployments can be connected to a device type. Device type refers to the model version, category or description of a kind of hardware, not the serial number of an individual device.',
  [STRING.TOOLTIP_JOB]:
    'A job is a request for data processing that specifies the data to process and the pipeline to use.',
  [STRING.TOOLTIP_OCCURRENCE]:
    'An occurrence refers to when an individual is detected in a sequence of one or more images with no time interruption.',
  [STRING.TOOLTIP_PIPELINE]:
    'A pipeline is a set of algorithms used for processing. A pipeline is picked from a list of algorithm bundle options when a processing job is defined.',
  [STRING.TOOLTIP_SESSION]:
    'A session is a fixed period of time of monitoring for one station. The period is typically one night.',
  [STRING.TOOLTIP_SITE]:
    'A site is a physical location where monitoring is taking place. One or many stations can be connected to a site.',
  [STRING.TOOLTIP_STATUS]:
    'A status is the processing stage of a job once submitted: Created > Pending > Started > Success. A Failed status means the job stopped before it had finished.',
  [STRING.TOOLTIP_STORAGE]:
    'A storage is a place where source images are kept, for example a S3 bucket. One or many stations can be connected to a storage.',

  /* OTHER */
  [STRING.ALGORITHMS]: 'Algorithms',
  [STRING.APPLY_ID]: 'Apply ID',
  [STRING.APPLY_ID_SHORT]: 'Apply',
  [STRING.BACK_TO_LOGIN]: 'Back to login',
  [STRING.CLOSE]: 'Close',
  [STRING.COLUMNS]: 'Columns',
  [STRING.CONNECTED]: 'Connected',
  [STRING.CONNECTING]: 'Connecting...',
  [STRING.FORGOT_PASSWORD]: 'Forgot password?',
  [STRING.FORGOT_PASSWORD_DETAILS]: `No worries, we'll send you reset instructions.`,
  [STRING.ID_APPLIED]: 'ID applied',
  [STRING.LAST_UPDATED]: 'Last updated',
  [STRING.LOADING_DATA]: 'Loading data',
  [STRING.MACHINE_PREDICTION_SCORE]: 'Machine prediction\nscore {{score}}',
  [STRING.MACHINE_SUGGESTION]: 'Machine suggestion',
  [STRING.NEW_ID]: 'New ID',
  [STRING.NOT_CONNECTED]: 'Not connected',
  [STRING.OR]: 'Or',
  [STRING.RECENT]: 'Recent',
  [STRING.REJECT_ID]: 'Reject ID',
  [STRING.REJECT_ID_SHORT]: 'Reject',
  [STRING.SELECT_COLUMNS]: 'Select columns',
  [STRING.RESULTS]: '{{total}} result(s)',
  [STRING.SET_PASSWORD]: 'Set password',
  [STRING.SET_PASSWORD_DETAILS]: 'Please set a new password for your acccount.',
  [STRING.STAGES]: 'Stages',
  [STRING.SUMMARY]: 'Summary',
  [STRING.UNKNOWN]: 'Unknown',
  [STRING.UNKNOWN_ERROR]: 'Unknown error',
  [STRING.UPDATING_DATA]: 'Updating data',
  [STRING.USER_INFO]: 'User info',
  [STRING.VERIFIED_BY]: 'Verified by\n{{name}}',
  [STRING.VALUE_NOT_AVAILABLE]: 'n/a',
}

// When we have more translations available, this function could return a value based on current language settings.
export const translate = (
  key: STRING,
  values?: { [key: string]: string | number }
): string => {
  let string = ENGLISH_STRINGS[key]

  if (!values) {
    return string
  }

  Object.entries(values).forEach(([key, value]) => {
    const valueLabel =
      typeof value === 'number' ? value.toLocaleString() : value
    string = string.replace(`{{${key}}}`, `${valueLabel}`)
  })

  return string
}
