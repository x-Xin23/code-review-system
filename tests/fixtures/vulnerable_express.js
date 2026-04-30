/**
 * Vulnerable Express Application - For Security Review Testing.
 *
 * Contains intentional vulnerabilities:
 * - SQL Injection (CWE-89)
 * - NoSQL Injection
 * - XSS (CWE-79)
 * - Command Injection (CWE-78)
 * - Path Traversal (CWE-22)
 * - SSRF (CWE-918)
 * - Hardcoded Secrets (CWE-798)
 * - Prototype Pollution
 * - Memory Leak (Performance)
 * - Race Condition (Logic)
 */

const express = require('express');
const mysql = require('mysql');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const app = express();

// VULNERABILITY: Hardcoded secrets (CWE-798)
const DB_PASSWORD = 'MyDatabasePassword123!';
const JWT_SECRET = 'hardcoded-jwt-secret-key';
const AWS_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE';
const AWS_SECRET_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY';

const connection = mysql.createConnection({
  host: 'localhost',
  user: 'admin',
  password: DB_PASSWORD,
  database: 'myapp',
});

// VULNERABILITY: SQL Injection (CWE-89)
app.get('/user', (req, res) => {
  const username = req.query.name;
  // Direct string concatenation into SQL query
  const query = `SELECT * FROM users WHERE name = '${username}'`;
  connection.query(query, (err, results) => {
    if (err) return res.status(500).send('Error');
    res.json(results);
  });
});

// VULNERABILITY: SQL injection via LIKE
app.get('/search', (req, res) => {
  const term = req.query.q;
  // Unsanitized input in LIKE clause
  connection.query(
    `SELECT * FROM products WHERE name LIKE '%${term}%'`,
    (err, results) => {
      res.json(results);
    }
  );
});

// VULNERABILITY: NoSQL Injection
const MongoClient = require('mongodb').MongoClient;
app.post('/login', express.json(), async (req, res) => {
  const { username, password } = req.body;
  const client = new MongoClient('mongodb://localhost:27017');
  await client.connect();
  const db = client.db('myapp');
  // Direct object injection: {"username": "admin", "password": {"$ne": ""}}
  const user = await db.collection('users').findOne({ username, password });
  if (user) {
    res.json({ token: JWT_SECRET });
  } else {
    res.status(401).send('Invalid credentials');
  }
  await client.close();
});

// VULNERABILITY: Command Injection (CWE-78)
app.get('/ping', (req, res) => {
  const host = req.query.host;
  // Unsanitized input passed to shell
  exec(`ping -c 1 ${host}`, (err, stdout, stderr) => {
    if (err) return res.status(500).send(stderr);
    res.send(`<pre>${stdout}</pre>`);
  });
});

// VULNERABILITY: Command injection via options
app.post('/convert', express.json(), (req, res) => {
  const { filename, options } = req.body;
  // Options string appended to command
  exec(`convert ${filename} ${options} output.png`, (err, stdout) => {
    res.send('Done');
  });
});

// VULNERABILITY: Path Traversal (CWE-22)
app.get('/file', (req, res) => {
  const filename = req.query.file;
  // Directory traversal possible with ../../etc/passwd
  const filePath = path.join('/var/app/uploads', filename);
  fs.readFile(filePath, 'utf8', (err, data) => {
    if (err) return res.status(500).send('Error reading file');
    res.send(data);
  });
});

// VULNERABILITY: SSRF (CWE-918)
const http = require('http');
app.get('/fetch', (req, res) => {
  const url = req.query.url;
  // Attacker can access internal services
  http.get(url, (response) => {
    let data = '';
    response.on('data', (chunk) => { data += chunk; });
    response.on('end', () => { res.send(data); });
  });
});

// VULNERABILITY: XSS (CWE-79)
app.get('/greet', (req, res) => {
  const name = req.query.name || 'Guest';
  // Reflected XSS - unescaped user input in HTML
  res.send(`<h1>Welcome, ${name}!</h1>`);
});

// VULNERABILITY: Prototype Pollution
app.post('/config', express.json(), (req, res) => {
  const config = {};
  // Deep merge without prototype checking
  function merge(target, source) {
    for (const key in source) {
      if (typeof source[key] === 'object') {
        target[key] = target[key] || {};
        merge(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
  }
  merge(config, req.body);
  res.json({ merged: config });
});

// VULNERABILITY: Memory Leak
const requestLogs = [];
app.use((req, res, next) => {
  // Unbounded array growth - memory leak
  requestLogs.push({
    url: req.url,
    headers: JSON.stringify(req.headers),
    body: JSON.stringify(req.body),
    timestamp: Date.now(),
  });
  next();
});

// VULNERABILITY: Race Condition
let inventory = { 'item-1': 100 };
app.post('/order', express.json(), (req, res) => {
  const { itemId, quantity } = req.body;
  // Read-modify-write without atomicity
  if (inventory[itemId] >= quantity) {
    // Simulate delay that creates race window
    setTimeout(() => {
      inventory[itemId] -= quantity;
    }, 0);
    res.json({ success: true, remaining: inventory[itemId] });
  } else {
    res.status(400).json({ error: 'Insufficient stock' });
  }
});

// VULNERABILITY: Open Redirect (CWE-601)
app.get('/redirect', (req, res) => {
  const target = req.query.url;
  // No URL validation
  res.redirect(target);
});

// VULNERABILITY: eval() with user input
app.post('/calculate', express.json(), (req, res) => {
  const expression = req.body.expression;
  // Direct eval of user input - RCE
  const result = eval(expression);
  res.json({ result });
});

// VULNERABILITY: Missing CORS / Security Headers
app.use((req, res, next) => {
  // Overly permissive CORS
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', '*');
  next();
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
