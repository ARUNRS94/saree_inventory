export interface User {
  user_id: number;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user?: User;
}

export interface RoleInfo {
  role: string;
  permissions: string[];
}

export interface Saree {
  saree_id: number;
  saree_code: string;
  saree_name: string;
  category: string | null;
  fabric: string | null;
  design_name: string | null;
  color: string | null;
  unit: string;
  created_date: string | null;
}

export interface Supplier {
  supplier_id: number;
  supplier_name: string;
  contact_person: string | null;
  phone: string | null;
  gst_no: string | null;
  address: string | null;
  contact_type: string;
  is_active: boolean;
  created_date: string | null;
}

export interface Vendor {
  vendor_id: number;
  vendor_name: string;
  process_type: string;
  contact_person: string | null;
  phone: string | null;
  gst_no: string | null;
  address: string | null;
  is_active: boolean;
  created_date: string | null;
}

export interface VendorProcessType {
  process_type_id: number;
  process_type: string;
  is_active: boolean;
  created_date: string | null;
}

export interface POItem {
  po_item_id: number;
  saree_id: number;
  saree_code: string | null;
  saree_name: string | null;
  stock_out_saree_id: number | null;
  stock_out_saree_code: string | null;
  target_fg_saree_id: number | null;
  target_fg_saree_code: string | null;
  target_fg_saree_name: string | null;
  ordered_qty: number;
  rate: number;
  amount: number;
}

export interface PurchaseOrder {
  po_id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string | null;
  contact_type: string | null;
  po_date: string;
  expected_date: string | null;
  status: string;
  remarks: string | null;
  items: POItem[];
}

export interface GRNItem {
  grn_item_id: number;
  saree_id: number;
  saree_code: string | null;
  saree_name: string | null;
  received_qty: number;
  damaged_qty: number;
  rate: number;
}

export interface GRN {
  grn_id: number;
  grn_number: string;
  po_id: number;
  po_number: string | null;
  grn_date: string;
  remarks: string | null;
  items: GRNItem[];
}

export interface JobWorkIssueItem {
  issue_item_id: number;
  saree_id: number;
  saree_code: string | null;
  saree_name: string | null;
  issued_qty: number;
}

export interface JobWorkIssue {
  issue_id: number;
  issue_no: string;
  vendor_id: number;
  vendor_name: string | null;
  issue_date: string;
  status: string;
  remarks: string | null;
  items: JobWorkIssueItem[];
}

export interface JobWorkReceiptItem {
  receipt_item_id: number;
  saree_id: number;
  saree_code: string | null;
  saree_name: string | null;
  received_qty: number;
  rejected_qty: number;
  process_cost: number;
}

export interface JobWorkReceipt {
  receipt_id: number;
  receipt_no: string;
  issue_id: number;
  issue_no: string | null;
  vendor_id: number;
  vendor_name: string | null;
  receipt_date: string;
  items: JobWorkReceiptItem[];
}

export interface StockSummary {
  saree_id: number;
  saree_code: string;
  saree_name: string;
  fabric: string | null;
  current_stock: number;
}

export interface StockValuation {
  saree_id: number;
  saree_code: string;
  saree_name: string;
  current_stock: number;
  latest_rate: number;
  value: number;
}

export interface StockLedgerEntry {
  ledger_id: number;
  transaction_date: string;
  transaction_type: string;
  reference_no: string;
  saree_id: number;
  saree_code: string | null;
  saree_name: string | null;
  qty_in: number;
  qty_out: number;
  rate: number;
  remarks: string | null;
}

export interface DashboardCards {
  total_stock_qty: number;
  stock_value: number;
  open_po_value: number;
  pending_po_qty: number;
  vendor_wip_qty: number;
  active_sarees: number;
  active_vendors: number;
  active_suppliers: number;
}

export interface DashboardData {
  cards: DashboardCards;
  purchase_trend: { month: string; value: number }[];
  stock_movement: { month: string; qty_in: number; qty_out: number }[];
  top_categories: { category: string; qty: number }[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
