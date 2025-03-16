// src/components/Dashboard.jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    Container,
    Paper,
    Box,
    Card,
    CardContent
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { logoutUser } from '../services/AuthService.js';
import Chart from './Chart';
import { CustomColors } from '../theme';

const Dashboard = () => {
    const { currentUser } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        try {
            await logoutUser();
            navigate('/login');
        } catch (error) {
            console.error("Logout error:", error);
        }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: CustomColors.UIGrey100 }}>
            <AppBar position="static" color="secondary">
                <Toolbar>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        Firebase + Vite Template
                    </Typography>
                    <Typography variant="bodySmall" sx={{ mr: 2 }}>
                        {currentUser?.email}
                    </Typography>
                    <Button
                        variant="outlined"
                        color="default"
                        onClick={handleLogout}
                        size="small"
                    >
                        Logout
                    </Button>
                </Toolbar>
            </AppBar>

            <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
                <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h4" component="h2" gutterBottom>
                        Dashboard
                    </Typography>
                    <Typography variant="body" color="text.secondary" gutterBottom>
                        Welcome to your dashboard! Below is an example chart created with ECharts.
                    </Typography>
                </Paper>

                <Card>
                    <CardContent>
                        <Typography variant="h5" component="h3" gutterBottom>
                            Sample Chart
                        </Typography>
                        <Box sx={{ height: 400 }}>
                            <Chart />
                        </Box>
                    </CardContent>
                </Card>
            </Container>
        </Box>
    );
};

export default Dashboard;