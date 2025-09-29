// src/components/Dashboard.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    Container,
    Box,
    Tabs,
    Tab
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { logoutUser } from '../services/AuthService.js';
import ContentFinder from './ContentFinder';
import IntelligenceDashboard from './intelligence/IntelligenceDashboard';
import VOCDiscovery from './intelligence/VOCDiscovery';
import { CustomColors } from '../theme';

const Dashboard = () => {
    const { currentUser } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState(0);

    const handleLogout = async () => {
        try {
            await logoutUser();
            navigate('/login');
        } catch (error) {
            console.error("Logout error:", error);
        }
    };

    const handleTabChange = (event, newValue) => {
        setActiveTab(newValue);
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: CustomColors.UIGrey100 }}>
            <AppBar position="static" color="secondary">
                <Toolbar>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        Content Finder - Outstaffer Intelligence
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
                <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
                    <Tabs value={activeTab} onChange={handleTabChange}>
                        <Tab label="Content Finder" />
                        <Tab label="Intelligence Engine" />
                        <Tab label="Trend Discovery" />
                    </Tabs>
                </Box>

                {activeTab === 0 && <ContentFinder />}
                {activeTab === 1 && <IntelligenceDashboard />}
                {activeTab === 2 && <VOCDiscovery />}
            </Container>
        </Box>
    );
};

export default Dashboard;
