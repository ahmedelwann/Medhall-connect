// Run locally to generate ADMIN_PASSWORD_HASH before deploying:
//   node scripts/hash-password.js "your-strong-password"
// Paste the printed hash into Vercel env var ADMIN_PASSWORD_HASH.
// Never commit the plaintext password or the hash to git.
const bcrypt = require('bcryptjs');

const password = process.argv[2];
if (!password) {
  console.error('Usage: node scripts/hash-password.js "your-strong-password"');
  process.exit(1);
}

const hash = bcrypt.hashSync(password, 12);
console.log(hash);
