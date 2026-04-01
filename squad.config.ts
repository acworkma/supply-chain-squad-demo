import type { SquadConfig } from '@bradygaster/squad';

/**
 * Squad Configuration for supply-chain-squad-demo
 * 
 */
const config: SquadConfig = {
  version: '1.0.0',
  
  models: {
    defaultModel: 'claude-sonnet-4.5',
    defaultTier: 'standard',
    fallbackChains: {
      premium: ['claude-opus-4.6', 'claude-opus-4.6-fast', 'claude-opus-4.5', 'claude-sonnet-4.5'],
      standard: ['claude-sonnet-4.5', 'gpt-5.2-codex', 'claude-sonnet-4', 'gpt-5.2'],
      fast: ['claude-haiku-4.5', 'gpt-5.1-codex-mini', 'gpt-4.1', 'gpt-5-mini']
    },
    preferSameProvider: true,
    respectTierCeiling: true,
    nuclearFallback: {
      enabled: false,
      model: 'claude-haiku-4.5',
      maxRetriesBeforeNuclear: 3
    }
  }
};

export default config;
