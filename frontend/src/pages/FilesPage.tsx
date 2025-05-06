import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Grid,
  Card,
  CardContent,
  CardActions,
  Divider,
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  CircularProgress,
  Snackbar,
  Alert,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import { useNavigate } from 'react-router-dom';

// Components
import FileUpload from '../components/common/FileUpload';

// Hooks
import { useMainWindowHooks } from '../hooks';

// Utils
import { formatBytes, formatDate } from '../utils/helpers';

const FilesPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  
  // Get file hooks from useMainWindowHooks
  const { file } = useMainWindowHooks();
  
  // Extract the needed file functionality
  const { 
    files, 
    isLoading, 
    uploadFiles, 
    deleteFile, 
    downloadFile 
  } = file;
  
  // UI state
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [alert, setAlert] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });
  
  // Handle file menu open
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, fileId: string) => {
    setMenuAnchorEl(event.currentTarget);
    setSelectedFileId(fileId);
  };
  
  // Handle file menu close
  const handleMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedFileId(null);
  };
  
  // Handle file deletion
  const handleDeleteFile = async () => {
    if (selectedFileId) {
      try {
        await deleteFile(selectedFileId);
        setAlert({
          open: true,
          message: 'File deleted successfully',
          severity: 'success',
        });
      } catch (err) {
        setAlert({
          open: true,
          message: 'Failed to delete file',
          severity: 'error',
        });
      }
      handleMenuClose();
    }
  };
  
  // Handle file download
  const handleDownloadFile = async () => {
    if (selectedFileId) {
      try {
        const success = await downloadFile(selectedFileId);
        if (success) {
          setAlert({
            open: true,
            message: 'File download started',
            severity: 'success',
          });
        } else {
          setAlert({
            open: true,
            message: 'Failed to download file',
            severity: 'error',
          });
        }
      } catch (err) {
        setAlert({
          open: true,
          message: 'Failed to download file',
          severity: 'error',
        });
      }
      handleMenuClose();
    }
  };
  
  // Handle file upload
  const handleFilesSelected = async (selectedFiles: File[]) => {
    if (selectedFiles.length === 0) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    
    try {
      // Set up progress tracking
      const progressCallback = (progress: number) => {
        setUploadProgress(progress);
      };
      
      // Upload the files
      await uploadFiles(selectedFiles, progressCallback);
      
      setAlert({
        open: true,
        message: `Successfully uploaded ${selectedFiles.length} file(s)`,
        severity: 'success',
      });
    } catch (err) {
      console.error('Error uploading files:', err);
      setAlert({
        open: true,
        message: err instanceof Error ? err.message : 'Failed to upload files',
        severity: 'error',
      });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };
  
  // Handle back navigation
  const handleBack = () => {
    navigate('/');
  };
  
  // Close alert
  const handleCloseAlert = () => {
    setAlert({ ...alert, open: false });
  };
  
  // Get appropriate icon for file type
  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) {
      return <ImageIcon fontSize="large" />;
    } else if (fileType === 'application/pdf') {
      return <PictureAsPdfIcon fontSize="large" />;
    } else if (fileType.includes('document') || fileType.includes('text')) {
      return <DescriptionIcon fontSize="large" />;
    } else {
      return <InsertDriveFileIcon fontSize="large" />;
    }
  };
  
  // Show error from useFiles hook
  useEffect(() => {
    if (file.fileActionError) {
      setAlert({
        open: true,
        message: file.fileActionError,
        severity: 'error',
      });
    }
  }, [file.fileActionError]);
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
        p: 3,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={handleBack} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1">
          Files Library
        </Typography>
      </Box>
      
      <Paper
        elevation={0}
        sx={{
          p: 3,
          backgroundColor: 'rgba(30, 30, 30, 0.6)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 2,
          flexGrow: 1,
          overflow: 'auto',
        }}
      >
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Upload Files
          </Typography>
          <FileUpload
            onFilesSelected={handleFilesSelected}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
            acceptedFileTypes={['image/*', 'application/pdf', 'text/*', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']}
          />
        </Box>
        
        <Divider sx={{ mb: 4 }} />
        
        <Typography variant="h6" gutterBottom>
          Files Library
        </Typography>
        
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
            <CircularProgress />
          </Box>
        ) : files.filter(file => !file.isDeleted).length === 0 ? (
          <Box sx={{ textAlign: 'center', my: 4 }}>
            <Typography variant="body1" color="text.secondary">
              You haven't uploaded any files yet
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {files.filter(file => !file.isDeleted).map(file => (
              <Grid item xs={12} sm={6} md={4} key={file.id}>
                <Card
                  variant="outlined"
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <Box
                    sx={{
                      p: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                      height: 100,
                    }}
                  >
                    {file.fileType.startsWith('image/') && file.storagePath ? (
                      <Box
                        component="img"
                        src={file.storagePath}
                        alt={file.filename}
                        sx={{
                          maxHeight: '100%',
                          maxWidth: '100%',
                          objectFit: 'contain',
                        }}
                      />
                    ) : (
                      <Box sx={{ color: 'primary.main' }}>
                        {getFileIcon(file.fileType)}
                      </Box>
                    )}
                  </Box>
                  
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle1" noWrap title={file.filename}>
                      {file.filename}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatBytes(file.fileSize)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Uploaded: {formatDate(file.createdAt)}
                    </Typography>
                  </CardContent>
                  
                  <CardActions sx={{ justifyContent: 'flex-end' }}>
                    <IconButton size="small" onClick={(e) => handleMenuOpen(e, file.id)}>
                      <MoreVertIcon fontSize="small" />
                    </IconButton>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Paper>
      
      {/* File menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleDeleteFile}>
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          Delete
        </MenuItem>
      </Menu>
      
      {/* Alert */}
      <Snackbar
        open={alert.open}
        autoHideDuration={6000}
        onClose={handleCloseAlert}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseAlert} severity={alert.severity}>
          {alert.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default FilesPage; 