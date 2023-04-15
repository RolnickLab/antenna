export enum STRING {
  /* BUTTON */
  DEQUE_ALL,
  QUEUE_ALL,
  RESET,
  SAVE_CHANGES,

  /* DETAILS_LABEL */
  DETAILS_LABEL_APPEARANCE,
  DETAILS_LABEL_AVG_TEMP,
  DETAILS_LABEL_AVG_WEATHER,
  DETAILS_LABEL_CAMERA,
  DETAILS_LABEL_DATE,
  DETAILS_LABEL_DEPLOYMENT,
  DETAILS_LABEL_DURATION,
  DETAILS_LABEL_ELEVATION,
  DETAILS_LABEL_LIGHT_SOURCE,
  DETAILS_LABEL_SESSION,
  DETAILS_LABEL_TIME,

  /* NAV_ITEM */
  NAV_ITEM_BATCH_ID,
  NAV_ITEM_DEPLOYMENTS,
  NAV_ITEM_OCCURRENCES,
  NAV_ITEM_OVERVIEW,
  NAV_ITEM_PROJECT,
  NAV_ITEM_SESSIONS,
  NAV_ITEM_SETTINGS,
  NAV_ITEM_SPECIES,

  /* TAB_ITEM */
  TAB_ITEM_CLASSIFICATION,
  TAB_ITEM_FIELDS,
  TAB_ITEM_GALLERY,
  TAB_ITEM_TABLE,

  /* TABLE_COLUMN */
  TABLE_COLUMN_ACTIONS,
  TABLE_COLUMN_APPEARANCE,
  TABLE_COLUMN_AVG_TEMP,
  TABLE_COLUMN_COMPLETE,
  TABLE_COLUMN_DATE,
  TABLE_COLUMN_DEPLOYMENT,
  TABLE_COLUMN_DESCRIPTION,
  TABLE_COLUMN_DETECTIONS,
  TABLE_COLUMN_DURATION,
  TABLE_COLUMN_ID,
  TABLE_COLUMN_IMAGES,
  TABLE_COLUMN_MOST_RECENT,
  TABLE_COLUMN_OCCURRENCES,
  TABLE_COLUMN_QUEUED,
  TABLE_COLUMN_SESSION,
  TABLE_COLUMN_SESSIONS,
  TABLE_COLUMN_SPECIES,
  TABLE_COLUMN_STATUS,
  TABLE_COLUMN_TIME,
  TABLE_COLUMN_UNPROCESSED,

  /* OTHER */
  CLOSE,
  RUNNING,
  SCORE,
  SELECT_COLUMNS,
  SELECT_PATH,
  SELECT_VALUE,
  SESSION,
  SETTINGS,
  STOPPED,
}

const ENGLISH_STRINGS: { [key in STRING]: string } = {
  /* BUTTON */
  [STRING.DEQUE_ALL]: 'Deque all',
  [STRING.QUEUE_ALL]: 'Queue all',
  [STRING.RESET]: 'Reset',
  [STRING.SAVE_CHANGES]: 'Save changes',

  /* DETAILS_LABEL */
  [STRING.DETAILS_LABEL_APPEARANCE]: 'Appearance',
  [STRING.DETAILS_LABEL_AVG_TEMP]: 'Avg temp',
  [STRING.DETAILS_LABEL_AVG_WEATHER]: 'Avg weather',
  [STRING.DETAILS_LABEL_CAMERA]: 'Camera',
  [STRING.DETAILS_LABEL_DATE]: 'Date',
  [STRING.DETAILS_LABEL_DEPLOYMENT]: 'Deployment',
  [STRING.DETAILS_LABEL_DURATION]: 'Duration',
  [STRING.DETAILS_LABEL_ELEVATION]: 'Elevation',
  [STRING.DETAILS_LABEL_LIGHT_SOURCE]: 'Light source',
  [STRING.DETAILS_LABEL_SESSION]: 'Session',
  [STRING.DETAILS_LABEL_TIME]: 'Time',

  /* NAV_ITEM */
  [STRING.NAV_ITEM_BATCH_ID]: 'Batch ID',
  [STRING.NAV_ITEM_DEPLOYMENTS]: 'Deployments',
  [STRING.NAV_ITEM_OCCURRENCES]: 'Occurrences',
  [STRING.NAV_ITEM_OVERVIEW]: 'Overview',
  [STRING.NAV_ITEM_PROJECT]: 'Project',
  [STRING.NAV_ITEM_SESSIONS]: 'Sessions',
  [STRING.NAV_ITEM_SETTINGS]: 'Settings',
  [STRING.NAV_ITEM_SPECIES]: 'Species',

  /* TAB_ITEM */
  [STRING.TAB_ITEM_CLASSIFICATION]: 'Classification',
  [STRING.TAB_ITEM_FIELDS]: 'Fields',
  [STRING.TAB_ITEM_GALLERY]: 'Gallery',
  [STRING.TAB_ITEM_TABLE]: 'Table',

  /* TABLE_COLUMN */
  [STRING.TABLE_COLUMN_ACTIONS]: 'Actions',
  [STRING.TABLE_COLUMN_APPEARANCE]: 'Appearance',
  [STRING.TABLE_COLUMN_AVG_TEMP]: 'Avg temp',
  [STRING.TABLE_COLUMN_COMPLETE]: 'Complete',
  [STRING.TABLE_COLUMN_DATE]: 'Date',
  [STRING.TABLE_COLUMN_DEPLOYMENT]: 'Deployment',
  [STRING.TABLE_COLUMN_DESCRIPTION]: 'Description',
  [STRING.TABLE_COLUMN_DETECTIONS]: 'Detections',
  [STRING.TABLE_COLUMN_DURATION]: 'Duration',
  [STRING.TABLE_COLUMN_ID]: 'ID',
  [STRING.TABLE_COLUMN_IMAGES]: 'Images',
  [STRING.TABLE_COLUMN_MOST_RECENT]: 'Most recent',
  [STRING.TABLE_COLUMN_OCCURRENCES]: 'Occurrences',
  [STRING.TABLE_COLUMN_QUEUED]: 'Queued',
  [STRING.TABLE_COLUMN_SESSION]: 'Session',
  [STRING.TABLE_COLUMN_SESSIONS]: 'Sessions',
  [STRING.TABLE_COLUMN_SPECIES]: 'Species',
  [STRING.TABLE_COLUMN_STATUS]: 'Status',
  [STRING.TABLE_COLUMN_TIME]: 'Time',
  [STRING.TABLE_COLUMN_UNPROCESSED]: 'Unprocessed',

  /* OTHER */
  [STRING.CLOSE]: 'Close',
  [STRING.RUNNING]: 'Running',
  [STRING.SCORE]: 'Score',
  [STRING.SELECT_COLUMNS]: 'Select columns',
  [STRING.SELECT_PATH]: 'Select a path',
  [STRING.SELECT_VALUE]: 'Select a value',
  [STRING.SESSION]: 'Session',
  [STRING.SETTINGS]: 'Settings',
  [STRING.STOPPED]: 'Stopped',
}

// When we have more translations available, this function could return a value based on current language settings.
export const translate = (key: STRING): string => {
  return ENGLISH_STRINGS[key]
}
