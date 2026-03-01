#!/usr/bin/env node

// Simple test to verify our frontend setup
const fs = require('fs');
const path = require('path');

console.log('🧪 Testing TeacherPilot Frontend Setup...\n');

// Test 1: Check if Tailwind config exists
const tailwindConfig = fs.existsSync(path.join(__dirname, 'tailwind.config.js'));
console.log(`✅ Tailwind config: ${tailwindConfig ? 'Found' : 'Missing'}`);

// Test 2: Check if PostCSS config exists
const postcssConfig = fs.existsSync(path.join(__dirname, 'postcss.config.js'));
console.log(`✅ PostCSS config: ${postcssConfig ? 'Found' : 'Missing'}`);

// Test 3: Check if TypeScript config exists
const tsConfig = fs.existsSync(path.join(__dirname, 'tsconfig.json'));
console.log(`✅ TypeScript config: ${tsConfig ? 'Found' : 'Missing'}`);

// Test 4: Check if ESLint config exists
const eslintConfig = fs.existsSync(path.join(__dirname, '.eslintrc.cjs'));
console.log(`✅ ESLint config: ${eslintConfig ? 'Found' : 'Missing'}`);

// Test 5: Check if Prettier config exists
const prettierConfig = fs.existsSync(path.join(__dirname, '.prettierrc'));
console.log(`✅ Prettier config: ${prettierConfig ? 'Found' : 'Missing'}`);

// Test 6: Check folder structure
const folders = [
  'src/app/routes',
  'src/app/providers',
  'src/components/ui',
  'src/components/features',
  'src/features/priorities',
  'src/features/schedule',
  'src/features/marimba',
  'src/lib/api',
  'src/lib/hooks',
  'src/lib/utils',
  'src/types'
];

console.log('\n📁 Folder Structure:');
folders.forEach(folder => {
  const exists = fs.existsSync(path.join(__dirname, 'src', folder));
  console.log(`  ${exists ? '✅' : '❌'} ${folder}`);
});

// Test 7: Check if Tailwind is in CSS
const cssContent = fs.readFileSync(path.join(__dirname, 'src', 'index.css'), 'utf8');
const hasTailwind = cssContent.includes('@tailwind');
console.log(`\n✅ Tailwind in CSS: ${hasTailwind ? 'Found' : 'Missing'}`);

// Test 8: Check package.json scripts
const packageJson = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
const requiredScripts = ['dev', 'build', 'lint', 'format', 'type-check', 'prepare'];
console.log('\n📋 Package.json scripts:');
requiredScripts.forEach(script => {
  const exists = packageJson.scripts && packageJson.scripts[script];
  console.log(`  ${exists ? '✅' : '❌'} ${script}`);
});

console.log('\n🎉 Frontend setup verification complete!');
console.log('\nNext steps:');
console.log('1. Run `npm install` to install dependencies');
console.log('2. Run `npm run dev` to start development server');
console.log('3. Run `npm run format` to format code');
console.log('4. Run `npm run lint` to check for linting errors');