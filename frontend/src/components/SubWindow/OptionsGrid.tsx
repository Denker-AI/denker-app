import React from 'react';
import { 
  Grid, 
  Card, 
  CardContent, 
  CardActionArea, 
  Typography, 
  Box 
} from '@mui/material';
import { Option } from '../../pages/SubWindow';

interface OptionsGridProps {
  options: Option[];
  onOptionSelect: (option: Option) => void;
}

const OptionsGrid: React.FC<OptionsGridProps> = ({ options, onOptionSelect }) => {
  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column',
      gap: 1,
      height: 'calc(100vh - 48px)', // Subtract NavBar height
      p: 1.5,
      overflowY: 'auto'
    }}>
      {options.map((option) => (
        <Card 
          key={option.id}
          sx={{ 
            backgroundColor: 'rgba(30, 30, 30, 0.8)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            transition: 'all 0.2s ease-in-out',
            flex: 1,
            display: 'flex',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)',
              borderColor: 'primary.main',
            }
          }}
        >
          <CardActionArea 
            onClick={() => onOptionSelect(option)}
            sx={{ 
              width: '100%', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'flex-start',
              py: 0.5,
              px: 1.5
            }}
          >
            <CardContent sx={{ p: 0, width: '100%' }}>
              <Typography 
                variant="body1" 
                component="div" 
                sx={{ 
                  fontSize: '0.9rem',
                  lineHeight: 1.4,
                  whiteSpace: 'normal',
                  wordBreak: 'break-word'
                }}
              >
                {option.title}
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
    </Box>
  );
};

export default OptionsGrid; 