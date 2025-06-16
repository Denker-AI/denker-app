import React from 'react';
import { Box, Typography } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DescriptionIcon from '@mui/icons-material/Description';
import TranslateIcon from '@mui/icons-material/Translate';
import CodeIcon from '@mui/icons-material/Code';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';

// Components
import SubWindowNavBar from '../components/SubWindow/SubWindowNavBar';
import OptionsGrid from '../components/SubWindow/OptionsGrid';
import LoadingIndicator from '../components/SubWindow/LoadingIndicator';
import ErrorIndicator from '../components/SubWindow/ErrorIndicator';

// Hooks
import { useSubWindow } from '../hooks/useSubWindow';

// Define the option type
export interface Option {
  id: string;
  title: string;
  description: string;
  icon?: React.ReactNode;
}

const SubWindow: React.FC = () => {
  const {
    isLoading,
    isAnalyzing,
    error,
    selectedText,
    options,
    handleOptionSelect,
    handleClose,
    openMainWindow
  } = useSubWindow();

  // Add icons to options
  const optionsWithIcons = options.map(option => {
    let icon;
    const title = option.title.toLowerCase();
    
    if (title.includes('search') || title.includes('find')) {
      icon = <SearchIcon />;
    } else if (title.includes('explain') || title.includes('analyze')) {
      icon = <DescriptionIcon />;
    } else if (title.includes('translate')) {
      icon = <TranslateIcon />;
    } else if (title.includes('code')) {
      icon = <CodeIcon />;
    } else {
      icon = <AutoFixHighIcon />;
    }
    
    return { ...option, icon };
  });

  // Determine what to show based on state
  const getContentComponent = () => {
    if (error) {
      return <ErrorIndicator message={error} />;
    }
    
    if (isAnalyzing) {
      return <LoadingIndicator message="Analyzing your content..." />;
    }
    
    if (options.length === 0) {
      return <LoadingIndicator message="No options available. Try again with different content." />;
    }
    
    return <OptionsGrid options={optionsWithIcons} onOptionSelect={handleOptionSelect} />;
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Navigation bar */}
      <SubWindowNavBar 
        selectedText={selectedText}
        onClose={handleClose}
        onOpenMainWindow={openMainWindow}
      />
      
      {/* Content area */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flexGrow: 1,
          overflow: 'hidden',
          backgroundColor: 'rgba(18, 18, 18, 0.7)',
          backdropFilter: 'blur(10px)',
        }}
      >
        {getContentComponent()}
      </Box>
    </Box>
  );
};

export default SubWindow; 