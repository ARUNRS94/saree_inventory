/** Contact type values are stored in the database exactly as written here. */
export const RM_VENDOR = 'Raw Material Vendor';
export const SUB_VENDOR = 'Sub vendor';
export const CUSTOMER = 'Customer';

export const CONTACT_TYPES = [RM_VENDOR, SUB_VENDOR, CUSTOMER];

export const CONTACT_TYPE_OPTIONS = CONTACT_TYPES.map((value) => ({ value, label: value }));
