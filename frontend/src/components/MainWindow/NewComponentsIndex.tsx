// This file serves as a transitional bridge to help migrate from legacy components to the new component system
// It re-exports all new components that are built using the hooks-based architecture

export { default as MainWindowNew } from '../../pages/MainWindowNew';
export { default as SideMenuNew } from './SideMenuNew';
export { default as ChatAreaNew } from './ChatAreaNew';
export { default as InputBoxNew } from './InputBoxNew';
export { default as NavBarNew } from './NavBarNew';

// Note: This file is meant to be a transitional bridge to help migrate from the legacy
// components to the new component system that uses our hooks-based architecture.
// Eventually, these would replace the original components. 