/**
 * Postinstall script for confluence-md npm package.
 * Downloads the correct platform-specific binary from GitHub Releases.
 */

const { createWriteStream, unlinkSync, chmodSync, renameSync, existsSync, mkdirSync } = require('fs');
const { readFile } = require('fs/promises');
const { createHash } = require('crypto');
const { join, dirname } = require('path');
const https = require('https');

// Package version (updated by CI before publish)
const packageJson = require('./package.json');
const VERSION = packageJson.version;

// GitHub release base URL
const GITHUB_RELEASE_URL = `https://github.com/bzoboki/Confluence.md/releases/download/v${VERSION}`;

// Binary naming convention
const PLATFORM_MAP = {
  darwin: { x64: 'confluence-md-macos-x64', arm64: 'confluence-md-macos-arm64' },
  linux: { x64: 'confluence-md-linux-x64' },
  win32: { x64: 'confluence-md-win-x64.exe' }
};

// Retry configuration
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 1000;

/**
 * Get the binary name for the current platform.
 */
function getBinaryName() {
  const platform = process.platform;
  const arch = process.arch;

  if (!PLATFORM_MAP[platform]) {
    throw new Error(
      `Unsupported platform: ${platform}. ` +
      `Supported platforms: darwin (macOS), linux, win32 (Windows).`
    );
  }

  const archMap = PLATFORM_MAP[platform];
  if (!archMap[arch]) {
    const supported = Object.keys(archMap).join(', ');
    throw new Error(
      `Unsupported architecture: ${arch} on ${platform}. ` +
      `Supported architectures for ${platform}: ${supported}.`
    );
  }

  return archMap[arch];
}

/**
 * Download a file from URL with retry logic.
 */
function downloadFile(url, destPath, retryCount = 0) {
  return new Promise((resolve, reject) => {
    const tempPath = destPath + '.tmp';
    
    // Ensure directory exists
    const dir = dirname(destPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }

    const file = createWriteStream(tempPath);
    
    const handleError = (error) => {
      // Clean up temp file
      file.close();
      try { unlinkSync(tempPath); } catch {}
      
      if (retryCount < MAX_RETRIES) {
        const delay = INITIAL_RETRY_DELAY_MS * Math.pow(2, retryCount);
        console.log(`  Retry ${retryCount + 1}/${MAX_RETRIES} in ${delay}ms...`);
        setTimeout(() => {
          downloadFile(url, destPath, retryCount + 1).then(resolve).catch(reject);
        }, delay);
      } else {
        reject(new Error(`Failed to download after ${MAX_RETRIES} retries: ${error.message}`));
      }
    };

    const request = https.get(url, (response) => {
      // Handle redirects (GitHub releases use redirects)
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        file.close();
        try { unlinkSync(tempPath); } catch {}
        return downloadFile(response.headers.location, destPath, retryCount).then(resolve).catch(reject);
      }

      if (response.statusCode !== 200) {
        handleError(new Error(`HTTP ${response.statusCode}: ${response.statusMessage}`));
        return;
      }

      response.pipe(file);
      
      file.on('finish', () => {
        file.close(() => {
          // Rename temp to final
          try {
            renameSync(tempPath, destPath);
            resolve();
          } catch (err) {
            try { unlinkSync(tempPath); } catch {}
            reject(err);
          }
        });
      });
    });

    request.on('error', handleError);
    file.on('error', handleError);
  });
}

/**
 * Calculate SHA256 hash of a file.
 */
async function calculateSha256(filePath) {
  const content = await readFile(filePath);
  return createHash('sha256').update(content).digest('hex');
}

/**
 * Download and parse checksums file.
 */
async function downloadChecksums() {
  const url = `${GITHUB_RELEASE_URL}/checksums.txt`;
  const tempPath = join(__dirname, 'bin', 'checksums.txt.tmp');
  
  await downloadFile(url, tempPath);
  
  const content = await readFile(tempPath, 'utf-8');
  const checksums = {};
  
  for (const line of content.split('\n')) {
    const match = line.match(/^([a-f0-9]{64})\s+(.+)$/i);
    if (match) {
      checksums[match[2].trim()] = match[1].toLowerCase();
    }
  }
  
  // Clean up
  try { unlinkSync(tempPath); } catch {}
  
  return checksums;
}

/**
 * Main installation function.
 */
async function install() {
  console.log('confluence-md: Installing binary...');
  
  // Get binary name for this platform
  let binaryName;
  try {
    binaryName = getBinaryName();
  } catch (error) {
    console.error(`\nError: ${error.message}`);
    console.error('\nFor manual installation, download the binary from:');
    console.error(`  ${GITHUB_RELEASE_URL.replace(`/v${VERSION}`, '')}`);
    process.exit(1);
  }
  
  console.log(`  Platform: ${process.platform}-${process.arch}`);
  console.log(`  Binary: ${binaryName}`);
  
  // Determine local binary path
  const isWindows = process.platform === 'win32';
  const localBinaryName = isWindows ? 'confluence-md-binary.exe' : 'confluence-md-binary';
  const binDir = join(__dirname, 'bin');
  const binaryPath = join(binDir, localBinaryName);
  
  try {
    // Download checksums first
    console.log('  Downloading checksums...');
    const checksums = await downloadChecksums();
    
    const expectedChecksum = checksums[binaryName];
    if (!expectedChecksum) {
      throw new Error(`Checksum not found for ${binaryName} in checksums.txt`);
    }
    
    // Download binary
    const binaryUrl = `${GITHUB_RELEASE_URL}/${binaryName}`;
    console.log(`  Downloading binary from GitHub Releases...`);
    await downloadFile(binaryUrl, binaryPath);
    
    // Verify checksum
    console.log('  Verifying SHA256 checksum...');
    const actualChecksum = await calculateSha256(binaryPath);
    
    if (actualChecksum !== expectedChecksum) {
      unlinkSync(binaryPath);
      throw new Error(
        `Checksum mismatch!\n` +
        `  Expected: ${expectedChecksum}\n` +
        `  Actual:   ${actualChecksum}\n` +
        `This could indicate a corrupted download or tampering.`
      );
    }
    
    // Make executable on Unix
    if (!isWindows) {
      chmodSync(binaryPath, 0o755);
    }
    
    console.log('  ✓ Installation complete!');
  } catch (error) {
    console.error(`\nInstallation failed: ${error.message}`);
    console.error('\nTroubleshooting:');
    console.error('  - Check your internet connection');
    console.error('  - If behind a proxy, set HTTP_PROXY/HTTPS_PROXY environment variables');
    console.error('  - For manual installation, download from:');
    console.error(`    ${GITHUB_RELEASE_URL}`);
    process.exit(1);
  }
}

// Run installation
install();
