import "server-only";
import { randomBytes, scrypt, timingSafeEqual, type ScryptOptions } from "node:crypto";

/*
 * Password hashing with scrypt (built into Node, no native add-ons).
 * Parameters follow OWASP's scrypt guidance (N=2^17, r=8, p=1).
 * Stored format: scrypt$<N>$<r>$<p>$<saltB64>$<hashB64>
 * Storing the parameters lets us raise them later without breaking old hashes.
 */
const N = 2 ** 17;
const R = 8;
const P = 1;
const KEY_LEN = 64;
// scrypt needs ~128 * N * r bytes of memory; give it headroom.
const MAX_MEM = 256 * 1024 * 1024;

function scryptAsync(password: string, salt: Buffer, keyLen: number, opts: ScryptOptions): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password.normalize("NFKC"), salt, keyLen, opts, (err, key) => (err ? reject(err) : resolve(key)));
  });
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await scryptAsync(password, salt, KEY_LEN, { N, r: R, p: P, maxmem: MAX_MEM });
  return ["scrypt", N, R, P, salt.toString("base64"), key.toString("base64")].join("$");
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const [, n, r, p, saltB64, hashB64] = parts;
  const expected = Buffer.from(hashB64, "base64");
  const key = await scryptAsync(password, Buffer.from(saltB64, "base64"), expected.length, {
    N: Number(n),
    r: Number(r),
    p: Number(p),
    maxmem: MAX_MEM,
  });
  return key.length === expected.length && timingSafeEqual(key, expected);
}

/**
 * A real hash of a random password. Verifying against it when an email is not
 * found makes "unknown email" take as long as "wrong password", so response
 * timing doesn't reveal which emails are registered.
 */
let dummyHash: Promise<string> | null = null;
export function getDummyHash(): Promise<string> {
  dummyHash ??= hashPassword(randomBytes(16).toString("hex"));
  return dummyHash;
}
