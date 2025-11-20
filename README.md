# Ruh

pronounced [ˈɹu] - rooh

> AI-powered product safety analysis for conscious consumers - detect harmful substances and find safer alternatives. 

**Eject** is a Chrome extension that analyzes products for harmful substances (allergens, PFAS, and other chemicals) and recommends safer alternatives - all powered by a Claude AI agent.

## What It Does

1. **Detects Products**: Automatically recognizes when you're viewing a product online
2. **Analyzes Safety**: Claude agent examines ingredients for allergens, PFAS, and other harmful substances
3. **Scores Harm Level**: Clear visual indicator (0-100) showing how safe/risky the product is
4. **Recommends Alternatives**: AI finds safer products with lower risk scores
5. **Monetizes Ethically**: Free for users, earns through affiliate links on recommended alternatives

## Architecture

- **Chrome Extension**: React + TypeScript frontend with content scripts and popup UI
- **Backend Agent**: Node.js server using Claude Agent SDK with WebFetch and WebSearch tools
- **AI Analysis**: Claude 3.5 Sonnet performs ingredient analysis and alternative discovery
- **Monetization**: Affiliate links on safer alternative products (transparent disclosure)

## Current Status

🚧 **Phase 1 - MVP Development** (See [PLAN.md](./PLAN.md) for full roadmap)

## Documentation

- **[PLAN.md](./PLAN.md)**: Complete technical architecture, implementation roadmap, and guiding principles
- More docs coming as we build

## Authors

Arshveer Gahir

## License

All Rights Reserved
