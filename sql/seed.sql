-- Seed data uses CURRENT_DATE so "last 30 days" / "last 6 months" stay valid.
-- Last completed quarter in the prompt is 2026-Q3 (today assumed Oct 2026).
-- Sales is the unique highest-revenue department for 2026-Q3.

INSERT INTO customers (customer_id, name, email, signup_date) VALUES
(1,  'Ada Sharma',       'ada.sharma@example.com',       CURRENT_DATE - INTERVAL '22 months'),
(2,  'Ben Okonkwo',      'ben.okonkwo@example.com',      CURRENT_DATE - INTERVAL '20 months'),
(3,  'Chen Wei',         'chen.wei@example.com',         CURRENT_DATE - INTERVAL '18 months'),
(4,  'Diana Patel',      'diana.patel@example.com',      CURRENT_DATE - INTERVAL '21 months'),
(5,  'Elena Rossi',      'elena.rossi@example.com',      CURRENT_DATE - INTERVAL '15 months'),
(6,  'Farid Hassan',     'farid.hassan@example.com',     CURRENT_DATE - INTERVAL '23 months'),
(7,  'Grace Kim',        'grace.kim@example.com',        CURRENT_DATE - INTERVAL '13 months'),
(8,  'Hiro Tanaka',      'hiro.tanaka@example.com',      CURRENT_DATE - INTERVAL '19 months'),
(9,  'Isla Berg',        'isla.berg@example.com',        CURRENT_DATE - INTERVAL '22 months'),
(10, 'Jamal Nwosu',      'jamal.nwosu@example.com',      CURRENT_DATE - INTERVAL '17 months'),
(11, 'Kavya Iyer',       'kavya.iyer@example.com',       CURRENT_DATE - INTERVAL '14 months'),
(12, 'Liam OBrien',      'liam.obrien@example.com',      CURRENT_DATE - INTERVAL '20 months'),
(13, 'Maya Singh',       'maya.singh@example.com',       CURRENT_DATE - INTERVAL '21 months'),
(14, 'Noah Becker',      'noah.becker@example.com',      CURRENT_DATE - INTERVAL '16 months'),
(15, 'Olivia Chen',      'olivia.chen@example.com',      CURRENT_DATE - INTERVAL '12 months'),
(16, 'Priya Nair',       'priya.nair@example.com',       CURRENT_DATE - INTERVAL '23 months');

SELECT setval('customers_customer_id_seq', (SELECT MAX(customer_id) FROM customers));

-- 48 orders over the last ~6 months.
-- Status mix ~60% completed / ~15% refunded / ~25% pending.
-- Eligible for refund (completed order within 30 days):
--   Ada, Ben, Chen, Grace, Kavya, Maya, Noah, Priya
INSERT INTO orders (order_id, customer_id, order_date, amount, status) VALUES
-- Ada (eligible)
(1,  1,  CURRENT_DATE - INTERVAL '19 days',  2400.00, 'completed'),
(2,  1,  CURRENT_DATE - INTERVAL '8 days',  10500.00, 'completed'),
(3,  1,  CURRENT_DATE - INTERVAL '65 days',  6400.00, 'completed'),
(4,  1,  CURRENT_DATE - INTERVAL '117 days', 1800.00, 'completed'),
-- Ben (eligible)
(5,  2,  CURRENT_DATE - INTERVAL '5 days',   5100.00, 'completed'),
(6,  2,  CURRENT_DATE - INTERVAL '140 days', 3200.00, 'completed'),
(7,  2,  CURRENT_DATE - INTERVAL '80 days',  2100.00, 'pending'),
-- Chen (eligible)
(8,  3,  CURRENT_DATE - INTERVAL '25 days',  8900.00, 'completed'),
(9,  3,  CURRENT_DATE - INTERVAL '98 days',  1100.00, 'completed'),
(10, 3,  CURRENT_DATE - INTERVAL '34 days',  1700.00, 'refunded'),
-- Diana (NOT eligible — recent order is pending)
(11, 4,  CURRENT_DATE - INTERVAL '17 days',  4500.00, 'pending'),
(12, 4,  CURRENT_DATE - INTERVAL '128 days',  900.00, 'completed'),
(13, 4,  CURRENT_DATE - INTERVAL '47 days',  5600.00, 'completed'),
-- Elena (NOT eligible — recent order is refunded)
(14, 5,  CURRENT_DATE - INTERVAL '15 days',  3300.00, 'refunded'),
(15, 5,  CURRENT_DATE - INTERVAL '150 days', 1500.00, 'completed'),
(16, 5,  CURRENT_DATE - INTERVAL '36 days',   750.00, 'pending'),
-- Farid (NOT eligible — completed orders older than 30 days)
(17, 6,  CURRENT_DATE - INTERVAL '84 days',  7200.00, 'completed'),
(18, 6,  CURRENT_DATE - INTERVAL '170 days',  800.00, 'completed'),
(19, 6,  CURRENT_DATE - INTERVAL '26 days',  3600.00, 'pending'),
-- Grace (eligible)
(20, 7,  CURRENT_DATE - INTERVAL '12 days',  1200.00, 'completed'),
(21, 7,  CURRENT_DATE - INTERVAL '28 days',  2300.00, 'completed'),
(22, 7,  CURRENT_DATE - INTERVAL '155 days',14900.00, 'completed'),
-- Hiro (NOT eligible — recent pending, completed too old)
(23, 8,  CURRENT_DATE - INTERVAL '6 days',   2600.00, 'pending'),
(24, 8,  CURRENT_DATE - INTERVAL '107 days', 3800.00, 'completed'),
(25, 8,  CURRENT_DATE - INTERVAL '89 days',  4200.00, 'completed'),
-- Isla (NOT eligible — recent refunded)
(26, 9,  CURRENT_DATE - INTERVAL '9 days',   4100.00, 'refunded'),
(27, 9,  CURRENT_DATE - INTERVAL '111 days', 1900.00, 'completed'),
(28, 9,  CURRENT_DATE - INTERVAL '145 days', 9900.00, 'completed'),
-- Jamal (NOT eligible — latest completed is 32 days ago)
(29, 10, CURRENT_DATE - INTERVAL '32 days',  1200.00, 'completed'),
(30, 10, CURRENT_DATE - INTERVAL '57 days',  5500.00, 'completed'),
(31, 10, CURRENT_DATE - INTERVAL '4 days',   2700.00, 'refunded'),
-- Kavya (eligible)
(32, 11, CURRENT_DATE - INTERVAL '23 days',   980.00, 'completed'),
(33, 11, CURRENT_DATE - INTERVAL '138 days', 4300.00, 'completed'),
(34, 11, CURRENT_DATE - INTERVAL '51 days',  3100.00, 'completed'),
-- Liam (NOT eligible — recent pending)
(35, 12, CURRENT_DATE - INTERVAL '29 days',   600.00, 'pending'),
(36, 12, CURRENT_DATE - INTERVAL '38 days', 12500.00, 'completed'),
(37, 12, CURRENT_DATE - INTERVAL '178 days', 8100.00, 'completed'),
-- Maya (eligible)
(38, 13, CURRENT_DATE - INTERVAL '7 days',   6700.00, 'completed'),
(39, 13, CURRENT_DATE - INTERVAL '90 days',  2100.00, 'pending'),
(40, 13, CURRENT_DATE - INTERVAL '92 days',  4400.00, 'completed'),
-- Noah (eligible)
(41, 14, CURRENT_DATE - INTERVAL '18 days',  7800.00, 'completed'),
(42, 14, CURRENT_DATE - INTERVAL '115 days', 3400.00, 'completed'),
(43, 14, CURRENT_DATE - INTERVAL '60 days',  1300.00, 'completed'),
-- Olivia (NOT eligible — recent pending, completed too old)
(44, 15, CURRENT_DATE - INTERVAL '35 days',  2200.00, 'completed'),
(45, 15, CURRENT_DATE - INTERVAL '2 days',   1500.00, 'pending'),
-- Priya (eligible)
(46, 16, CURRENT_DATE - INTERVAL '21 days',  9100.00, 'completed'),
(47, 16, CURRENT_DATE - INTERVAL '162 days',  500.00, 'refunded'),
(48, 16, CURRENT_DATE - INTERVAL '43 days',  1800.00, 'completed');

SELECT setval('orders_order_id_seq', (SELECT MAX(order_id) FROM orders));

INSERT INTO departments (department_id, name) VALUES
(1, 'Sales'),
(2, 'Marketing'),
(3, 'Engineering'),
(4, 'Support'),
(5, 'Operations');

SELECT setval('departments_department_id_seq', (SELECT MAX(department_id) FROM departments));

-- Four quarters. 2026-Q3 Sales is the unique max (985000).
INSERT INTO revenue (department_id, quarter, amount) VALUES
(1, '2025-Q4', 610000.00),
(2, '2025-Q4', 720000.00),
(3, '2025-Q4', 455000.00),
(4, '2025-Q4', 198000.00),
(5, '2025-Q4', 301000.00),
(1, '2026-Q1', 540000.00),
(2, '2026-Q1', 388000.00),
(3, '2026-Q1', 802000.00),
(4, '2026-Q1', 210000.00),
(5, '2026-Q1', 267000.00),
(1, '2026-Q2', 701000.00),
(2, '2026-Q2', 450000.00),
(3, '2026-Q2', 512000.00),
(4, '2026-Q2', 189000.00),
(5, '2026-Q2', 330000.00),
(1, '2026-Q3', 985000.00),
(2, '2026-Q3', 412000.00),
(3, '2026-Q3', 305000.00),
(4, '2026-Q3', 178000.00),
(5, '2026-Q3', 246000.00);
